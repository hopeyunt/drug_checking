import json
import os
from datetime import datetime, timezone
from itertools import combinations

import joblib
import numpy as np

from app.tasks.celery_app import celery_app
from app.core.database import get_sync_db
from app.core.config import settings
from app.models.interaction import InteractionCheck
from app.models.user import User
from app.services.billing_service import sync_deduct_credits, recalculate_loyalty

# Загружаем модель и метаданные один раз при старте воркера (кэш в памяти)
_model = None
_meta = None


def _load_model():
    # TODO: переделать на async когда будет время
    global _model, _meta
    if _model is None:
        _model = joblib.load(settings.MODEL_PATH)
    meta_path = settings.MODEL_PATH.replace(".joblib", "_meta.json").replace("interaction_model", "model")
    meta_file = os.path.join(os.path.dirname(settings.MODEL_PATH), "model_meta.json")
    if _meta is None and os.path.exists(meta_file):
        with open(meta_file, encoding="utf-8") as f:
            _meta = json.load(f)
    return _model, _meta


def _drug_to_features(drug_name: str, meta: dict) -> dict:
    drug_lower = drug_name.lower()
    drug_classes = meta.get("drug_classes", [])

    class_keywords = {
        "ACE_inhibitor": ["периндоприл", "эналаприл", "лизиноприл", "рамиприл", "captopril", "perindopril", "enalapril"],
        "ARB": ["лозартан", "валсартан", "кандесартан", "losartan", "valsartan"],
        "beta_blocker": ["метопролол", "бисопролол", "карведилол", "metoprolol", "bisoprolol"],
        "calcium_channel_blocker": ["амлодипин", "нифедипин", "верапамил", "amlodipine"],
        "diuretic_thiazide": ["индапамид", "гидрохлортиазид", "indapamide"],
        "diuretic_loop": ["фуросемид", "торасемид", "furosemide"],
        "statin": ["аторвастатин", "розувастатин", "симвастатин", "atorvastatin", "rosuvastatin"],
        "anticoagulant_warfarin": ["варфарин", "warfarin"],
        "anticoagulant_noac": ["ривароксабан", "апиксабан", "дабигатран", "rivaroxaban", "apixaban"],
        "antiplatelet": ["клопидогрел", "аспирин", "тикагрелор", "clopidogrel", "aspirin"],
        "NSAID": ["ибупрофен", "диклофенак", "напроксен", "ibuprofen", "diclofenac"],
        "opioid": ["морфин", "трамадол", "кодеин", "morphine", "tramadol"],
        "benzo": ["диазепам", "лоразепам", "алпразолам", "diazepam"],
        "SSRI": ["флуоксетин", "сертралин", "пароксетин", "fluoxetine", "sertraline"],
        "SNRI": ["венлафаксин", "дулоксетин", "venlafaxine", "duloxetine"],
        "TCA": ["амитриптилин", "имипрамин", "amitriptyline"],
        "antipsychotic_typical": ["галоперидол", "хлорпромазин", "haloperidol"],
        "antipsychotic_atypical": ["оланзапин", "рисперидон", "olanzapine", "risperidone"],
        "antibiotic_fluoroquinolone": ["ципрофлоксацин", "левофлоксацин", "ciprofloxacin"],
        "antibiotic_macrolide": ["азитромицин", "кларитромицин", "azithromycin", "clarithromycin"],
        "antibiotic_aminoglycoside": ["гентамицин", "амикацин", "gentamicin"],
        "antifungal_azole": ["флуконазол", "итраконазол", "fluconazole", "itraconazole"],
        "metformin": ["метформин", "metformin"],
        "sulfonylurea": ["глибенкламид", "глимепирид", "glibenclamide"],
        "insulin": ["инсулин", "insulin"],
        "digoxin": ["дигоксин", "digoxin"],
        "PPI": ["омепразол", "пантопразол", "омез", "omeprazole", "pantoprazole"],
        "corticosteroid": ["преднизолон", "дексаметазон", "prednisolone", "dexamethasone"],
        "immunosuppressant": ["циклоспорин", "такролимус", "cyclosporine"],
        "antiepileptic_CYP_inducer": ["карбамазепин", "фенитоин", "carbamazepine", "phenytoin"],
        "antiepileptic_CYP_inhibitor": ["вальпроевая", "valproate", "valproic"],
    }

    detected_class = "unknown"
    class_idx = 0
    for cls, keywords in class_keywords.items():
        if any(kw in drug_lower for kw in keywords):
            detected_class = cls
            if cls in drug_classes:
                class_idx = drug_classes.index(cls)
            break

    cyp_inhibitor = int(detected_class in ["antifungal_azole", "antibiotic_macrolide", "antiepileptic_CYP_inhibitor"])
    cyp_inducer   = int(detected_class in ["antiepileptic_CYP_inducer"])
    qt_risk       = int(detected_class in ["TCA", "antipsychotic_typical", "antibiotic_fluoroquinolone"])
    bleeding_risk = int(detected_class in ["anticoagulant_warfarin", "anticoagulant_noac", "NSAID", "antiplatelet"])
    renal_risk    = int(detected_class in ["antibiotic_aminoglycoside", "NSAID"])

    return {
        "class_idx":     class_idx,
        "drug_class":    detected_class,
        "cyp_inhibitor": cyp_inhibitor,
        "cyp_inducer":   cyp_inducer,
        "qt_risk":       qt_risk,
        "bleeding_risk": bleeding_risk,
        "renal_risk":    renal_risk,
    }


def _predict_pair(model, meta: dict, drug_a: str, drug_b: str) -> dict:
    fa = _drug_to_features(drug_a, meta)
    fb = _drug_to_features(drug_b, meta)

    features = np.array([[
        fa["class_idx"],
        fb["class_idx"],
        max(fa["cyp_inhibitor"], fb["cyp_inhibitor"]),
        max(fa["cyp_inducer"], fb["cyp_inducer"]),
        max(fa["qt_risk"], fb["qt_risk"]),
        max(fa["bleeding_risk"], fb["bleeding_risk"]),
        max(fa["renal_risk"], fb["renal_risk"]),
        int(fa["drug_class"] == fb["drug_class"] and fa["drug_class"] != "unknown"),
    ]])

    severity_idx = int(model.predict(features)[0])
    proba = model.predict_proba(features)[0]
    severity_score = float(proba[severity_idx])

    severity_labels = meta.get("severity_labels", {})
    descriptions = meta.get("severity_descriptions", {})
    recommendations = meta.get("severity_recommendations", {})

    severity_label = severity_labels.get(str(severity_idx), "unknown")
    return {
        "drug_a":          drug_a,
        "drug_b":          drug_b,
        "severity":        severity_label,
        "severity_score":  round(severity_score, 3),
        "description":     descriptions.get(str(severity_idx), ""),
        "recommendation":  recommendations.get(str(severity_idx), ""),
    }


@celery_app.task(
    name="app.tasks.interaction_tasks.run_interaction_check",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def run_interaction_check(self, check_id: int):
    db = next(get_sync_db())
    try:
        from sqlalchemy import select as sync_select
        check = db.execute(
            sync_select(InteractionCheck).where(InteractionCheck.id == check_id).with_for_update()
        ).scalar_one()

        check.status = "processing"
        db.commit()

        model, meta = _load_model()
        drugs = check.drugs_input if isinstance(check.drugs_input, list) else []

        interactions = []
        for drug_a, drug_b in combinations(drugs, 2):
            result = _predict_pair(model, meta, drug_a, drug_b)
            if result["severity"] != "none":
                interactions.append(result)

        interactions.sort(
            key=lambda x: ["none", "mild", "moderate", "severe", "contraindicated"].index(x["severity"]),
            reverse=True,
        )

        user = db.execute(
            sync_select(User).where(User.id == check.user_id)
        ).scalar_one()

        new_balance = sync_deduct_credits(
            db, check.user_id, check_id, check.cost,
            description=f"Проверка взаимодействий: {', '.join(drugs[:3])}{'...' if len(drugs) > 3 else ''}",
        )

        check.status = "completed"
        check.result = interactions
        check.interactions_found = len(interactions)
        check.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as exc:
        db.rollback()
        try:
            from sqlalchemy import select as sync_select
            check = db.execute(
                sync_select(InteractionCheck).where(InteractionCheck.id == check_id)
            ).scalar_one_or_none()
            if check:
                check.status = "failed"
                check.error_message = str(exc)
                db.commit()
        except Exception:
            pass

        raise self.retry(exc=exc)
    finally:
        db.close()
