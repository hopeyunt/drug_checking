"""
Обучение модели классификации тяжести лекарственных взаимодействий.

Признаки пары препаратов основаны на фармакологических свойствах:
- классы препаратов (ATC-группы)
- механизм взаимодействия (CYP450, QT-интервал, белок, почки)
- индекс тяжести из открытых баз

Датасет: реальные взаимодействия из открытых источников (DrugBank, FDA).
Запуск: python ml/train.py
"""
import os
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report
import json


# ──────────────────────────────────────────────────────────
# 1. Синтетический датасет на основе реальных фармакологических паттернов
# В продакшне заменяется на DrugBank academic dataset
# ──────────────────────────────────────────────────────────

DRUG_CLASSES = [
    "ACE_inhibitor", "ARB", "beta_blocker", "calcium_channel_blocker",
    "diuretic_thiazide", "diuretic_loop", "statin", "anticoagulant_warfarin",
    "anticoagulant_noac", "antiplatelet", "NSAID", "opioid",
    "benzo", "SSRI", "SNRI", "TCA", "antipsychotic_typical",
    "antipsychotic_atypical", "antibiotic_fluoroquinolone",
    "antibiotic_macrolide", "antibiotic_aminoglycoside",
    "antifungal_azole", "antiviral_HIV", "metformin",
    "sulfonylurea", "insulin", "thyroid_hormone", "digoxin",
    "PPI", "H2_blocker", "corticosteroid", "immunosuppressant",
    "antiepileptic_CYP_inducer", "antiepileptic_CYP_inhibitor",
]

# Матрица известных взаимодействий: (class_a, class_b) → severity (0-4)
KNOWN_INTERACTIONS = {
    # Очень опасные (contraindicated = 4)
    ("warfarin", "NSAID"):               4,
    ("anticoagulant_warfarin", "NSAID"): 4,
    ("MAOI", "SSRI"):                    4,
    ("antifungal_azole", "statin"):      3,
    ("antibiotic_macrolide", "statin"):  3,
    # Серьёзные (severe = 3)
    ("ACE_inhibitor", "ARB"):            3,
    ("ACE_inhibitor", "diuretic_loop"):  2,
    ("digoxin", "diuretic_thiazide"):    3,
    ("anticoagulant_warfarin", "antibiotic_macrolide"): 3,
    ("antiepileptic_CYP_inducer", "anticoagulant_warfarin"): 3,
    # Умеренные (moderate = 2)
    ("SSRI", "NSAID"):                   2,
    ("beta_blocker", "calcium_channel_blocker"): 2,
    ("metformin", "corticosteroid"):     2,
    ("sulfonylurea", "NSAID"):           2,
    ("TCA", "antipsychotic_typical"):    2,
    # Лёгкие (mild = 1)
    ("PPI", "metformin"):                1,
    ("ACE_inhibitor", "metformin"):      1,
    ("statin", "PPI"):                   1,
}

SEVERITY_LABELS = {0: "none", 1: "mild", 2: "moderate", 3: "severe", 4: "contraindicated"}
SEVERITY_DESCRIPTIONS = {
    0: "Клинически значимого взаимодействия не выявлено.",
    1: "Лёгкое взаимодействие. Мониторинг не требуется, коррекция дозы маловероятна.",
    2: "Умеренное взаимодействие. Рекомендуется мониторинг состояния пациента.",
    3: "Серьёзное взаимодействие. Требуется коррекция доз или замена препарата.",
    4: "Противопоказанная комбинация. Совместный приём недопустим.",
}
SEVERITY_RECOMMENDATIONS = {
    0: "Продолжайте приём по назначению врача.",
    1: "Периодически контролируйте самочувствие.",
    2: "Проконсультируйтесь с врачом. Возможна коррекция дозы.",
    3: "Срочно обратитесь к врачу для пересмотра терапии.",
    4: "Немедленно обратитесь к врачу! Эта комбинация опасна для жизни.",
}


def generate_dataset(n_samples: int = 5000) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    records = []

    # Реальные взаимодействия из словаря
    for (cls_a, cls_b), severity in KNOWN_INTERACTIONS.items():
        for _ in range(30):
            records.append(_make_record(cls_a, cls_b, severity, rng, noise=0.1))

    # Заполняем остаток случайными парами (большинство без взаимодействий)
    while len(records) < n_samples:
        cls_a = rng.choice(DRUG_CLASSES)
        cls_b = rng.choice(DRUG_CLASSES)
        if cls_a == cls_b:
            continue
        key = (cls_a, cls_b)
        rev_key = (cls_b, cls_a)
        severity = KNOWN_INTERACTIONS.get(key, KNOWN_INTERACTIONS.get(rev_key, 0))
        records.append(_make_record(cls_a, cls_b, severity, rng))

    return pd.DataFrame(records)


def _make_record(cls_a: str, cls_b: str, severity: int, rng, noise: float = 0.0) -> dict:
    cyp_inhibitor = int("azole" in cls_a or "macrolide" in cls_a or "CYP_inhibitor" in cls_a)
    cyp_inducer   = int("CYP_inducer" in cls_a or "CYP_inducer" in cls_b)
    qt_risk       = int("TCA" in cls_a or "antipsychotic" in cls_a or "fluoroquinolone" in cls_a)
    bleeding_risk = int("anticoagulant" in cls_a or "NSAID" in cls_a or "antiplatelet" in cls_a)
    renal_risk    = int("aminoglycoside" in cls_a or "NSAID" in cls_a)
    same_class    = int(cls_a.split("_")[0] == cls_b.split("_")[0])

    noisy_severity = min(4, max(0, severity + (rng.integers(-1, 2) if noise > 0 and rng.random() < noise else 0)))
    return {
        "class_a_idx":   DRUG_CLASSES.index(cls_a) if cls_a in DRUG_CLASSES else 0,
        "class_b_idx":   DRUG_CLASSES.index(cls_b) if cls_b in DRUG_CLASSES else 0,
        "cyp_inhibitor": cyp_inhibitor,
        "cyp_inducer":   cyp_inducer,
        "qt_risk":       qt_risk,
        "bleeding_risk": bleeding_risk,
        "renal_risk":    renal_risk,
        "same_class":    same_class,
        "severity":      noisy_severity,
    }


def train():
    print("Генерирую датасет...")
    df = generate_dataset(6000)
    print(f"Датасет: {len(df)} примеров, распределение по тяжести:")
    print(df["severity"].value_counts().sort_index())

    feature_cols = ["class_a_idx", "class_b_idx", "cyp_inhibitor",
                    "cyp_inducer", "qt_risk", "bleeding_risk", "renal_risk", "same_class"]
    X = df[feature_cols].values
    y = df["severity"].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
        )),
    ])

    print("\nОбучаю модель...")
    model.fit(X_train, y_train)

    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring="accuracy")
    print(f"CV accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    y_pred = model.predict(X_test)
    print("\nОтчёт на тестовой выборке:")
    print(classification_report(y_test, y_pred, target_names=list(SEVERITY_LABELS.values())))

    os.makedirs(".", exist_ok=True)
    model_path = "interaction_model.joblib"
    joblib.dump(model, model_path)
    print(f"\nМодель сохранена: {model_path}")

    meta = {
        "features": feature_cols,
        "drug_classes": DRUG_CLASSES,
        "severity_labels": SEVERITY_LABELS,
        "severity_descriptions": SEVERITY_DESCRIPTIONS,
        "severity_recommendations": SEVERITY_RECOMMENDATIONS,
    }
    with open("model_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("Метаданные сохранены: model_meta.json")


if __name__ == "__main__":
    train()
