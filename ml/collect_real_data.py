"""
Сбор реальных данных о лекарственных взаимодействиях через OpenFDA API (FDA/NIH).

Источник: официальные инструкции по применению препаратов (FDA drug labels).
API: https://api.fda.gov/drug/label.json  — бесплатно, без регистрации.

Методология:
  1. Для каждого препарата загружаем его FDA-инструкцию
  2. В разделах contraindications / warnings / drug_interactions ищем упоминания
     других препаратов из нашего списка
  3. По контексту вокруг упоминания определяем тяжесть взаимодействия:
       4 (contraindicated) — "contraindicated", "must not be used"
       3 (severe)          — "avoid", "serious", "life-threatening", "do not use"
       2 (moderate)        — "monitor", "caution", "reduce dose", "adjust"
       1 (mild)            — любое другое упоминание в разделе взаимодействий

Запуск: python ml/collect_real_data.py
"""
import csv
import re
import time
from pathlib import Path

import requests

FDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
WINDOW = 200  # символов вокруг упоминания для определения контекста

# Препарат → (generic name для запроса к FDA, фармакологический класс)
DRUG_REGISTRY: dict[str, tuple[str, str]] = {
    # Антикоагулянты
    "warfarin":            ("warfarin",            "anticoagulant_warfarin"),
    "rivaroxaban":         ("rivaroxaban",          "anticoagulant_noac"),
    "apixaban":            ("apixaban",             "anticoagulant_noac"),
    "dabigatran":          ("dabigatran",           "anticoagulant_noac"),
    # Антиагреганты
    "aspirin":             ("aspirin",              "antiplatelet"),
    "clopidogrel":         ("clopidogrel",          "antiplatelet"),
    # НПВС
    "ibuprofen":           ("ibuprofen",            "NSAID"),
    "naproxen":            ("naproxen",             "NSAID"),
    "diclofenac":          ("diclofenac",           "NSAID"),
    # Статины
    "simvastatin":         ("simvastatin",          "statin"),
    "atorvastatin":        ("atorvastatin",         "statin"),
    "lovastatin":          ("lovastatin",           "statin"),
    # Сахароснижающие
    "metformin":           ("metformin",            "metformin"),
    "glibenclamide":       ("glyburide",            "sulfonylurea"),
    "glipizide":           ("glipizide",            "sulfonylurea"),
    "insulin glargine":    ("insulin glargine",     "insulin"),
    # Прочие
    "levothyroxine":       ("levothyroxine",        "thyroid_hormone"),
    "digoxin":             ("digoxin",              "digoxin"),
    # иАПФ
    "lisinopril":          ("lisinopril",           "ACE_inhibitor"),
    "enalapril":           ("enalapril",            "ACE_inhibitor"),
    "ramipril":            ("ramipril",             "ACE_inhibitor"),
    # БРА
    "losartan":            ("losartan",             "ARB"),
    "valsartan":           ("valsartan",            "ARB"),
    # Бета-блокаторы
    "metoprolol":          ("metoprolol",           "beta_blocker"),
    "atenolol":            ("atenolol",             "beta_blocker"),
    "carvedilol":          ("carvedilol",           "beta_blocker"),
    # БМКК
    "amlodipine":          ("amlodipine",           "calcium_channel_blocker"),
    "verapamil":           ("verapamil",            "calcium_channel_blocker"),
    "diltiazem":           ("diltiazem",            "calcium_channel_blocker"),
    # Диуретики
    "furosemide":          ("furosemide",           "diuretic_loop"),
    "hydrochlorothiazide": ("hydrochlorothiazide",  "diuretic_thiazide"),
    # Азольные антигрибковые
    "fluconazole":         ("fluconazole",          "antifungal_azole"),
    "itraconazole":        ("itraconazole",         "antifungal_azole"),
    "ketoconazole":        ("ketoconazole",         "antifungal_azole"),
    # Макролиды
    "clarithromycin":      ("clarithromycin",       "antibiotic_macrolide"),
    "erythromycin":        ("erythromycin",         "antibiotic_macrolide"),
    # Фторхинолоны
    "ciprofloxacin":       ("ciprofloxacin",        "antibiotic_fluoroquinolone"),
    "levofloxacin":        ("levofloxacin",         "antibiotic_fluoroquinolone"),
    # Аминогликозиды
    "gentamicin":          ("gentamicin",           "antibiotic_aminoglycoside"),
    "amikacin":            ("amikacin",             "antibiotic_aminoglycoside"),
    # ВИЧ-препараты
    "ritonavir":           ("ritonavir",            "antiviral_HIV"),
    "lopinavir":           ("lopinavir",            "antiviral_HIV"),
    # Антиэпилептики
    "carbamazepine":       ("carbamazepine",        "antiepileptic_CYP_inducer"),
    "phenytoin":           ("phenytoin",            "antiepileptic_CYP_inducer"),
    "valproic acid":       ("valproic acid",        "antiepileptic_CYP_inhibitor"),
    # Иммунодепрессанты
    "cyclosporine":        ("cyclosporine",         "immunosuppressant"),
    "tacrolimus":          ("tacrolimus",           "immunosuppressant"),
    # Антипсихотики
    "haloperidol":         ("haloperidol",          "antipsychotic_typical"),
    "clozapine":           ("clozapine",            "antipsychotic_atypical"),
    "olanzapine":          ("olanzapine",           "antipsychotic_atypical"),
    "risperidone":         ("risperidone",          "antipsychotic_atypical"),
    # СИОЗС
    "sertraline":          ("sertraline",           "SSRI"),
    "fluoxetine":          ("fluoxetine",           "SSRI"),
    "paroxetine":          ("paroxetine",           "SSRI"),
    # СИОЗСН
    "venlafaxine":         ("venlafaxine",          "SNRI"),
    "duloxetine":          ("duloxetine",           "SNRI"),
    # ТЦА
    "amitriptyline":       ("amitriptyline",        "TCA"),
    "nortriptyline":       ("nortriptyline",        "TCA"),
    # Опиоиды
    "morphine":            ("morphine",             "opioid"),
    "oxycodone":           ("oxycodone",            "opioid"),
    "tramadol":            ("tramadol",             "opioid"),
    "fentanyl":            ("fentanyl",             "opioid"),
    # Бензодиазепины
    "diazepam":            ("diazepam",             "benzo"),
    "alprazolam":          ("alprazolam",           "benzo"),
    "clonazepam":          ("clonazepam",           "benzo"),
    # ИПП и Н2-блокаторы
    "omeprazole":          ("omeprazole",           "PPI"),
    "pantoprazole":        ("pantoprazole",         "PPI"),
    "ranitidine":          ("ranitidine",           "H2_blocker"),
    # Кортикостероиды
    "prednisone":          ("prednisone",           "corticosteroid"),
    "dexamethasone":       ("dexamethasone",        "corticosteroid"),
}

# Ключевые слова FDA для определения тяжести по контексту
SEVERITY_PATTERNS: list[tuple[int, list[str]]] = [
    (4, ["contraindicated", "must not be used", "must not be administered",
         "should not be used concomitantly", "is contraindicated"]),
    (3, ["avoid", "do not use", "do not administer", "should not be taken",
         "serious", "life-threatening", "fatal", "potentially fatal",
         "severe", "should be avoided"]),
    (2, ["monitor", "caution", "use caution", "closely monitor", "monitor closely",
         "reduce dose", "dose reduction", "adjust dose", "increased risk"]),
]


def _classify_severity(context: str) -> int:
    """Определяет тяжесть взаимодействия по контексту вокруг упоминания препарата."""
    ctx = context.lower()
    for severity, keywords in SEVERITY_PATTERNS:
        if any(kw in ctx for kw in keywords):
            return severity
    return 1  # mild — упомянут в разделе взаимодействий, но без строгих предупреждений


def _fetch_label(generic_name: str):
    """Загружает FDA-инструкцию для препарата."""
    params = {
        "search": f'openfda.generic_name:"{generic_name}"',
        "limit": 1,
    }
    try:
        resp = requests.get(FDA_LABEL_URL, params=params, timeout=15)
        if resp.status_code != 200:
            return None
        results = resp.json().get("results", [])
        return results[0] if results else None
    except Exception:
        return None


def _extract_interactions(label: dict, target_drugs: dict[str, str]) -> list[dict]:
    """
    Ищет упоминания целевых препаратов в разделах взаимодействий FDA-инструкции.
    Возвращает пары (target_name, severity).
    """
    # Собираем текст из релевантных секций
    sections = {
        "contraindications": 4,    # если препарат здесь — минимум 4
        "boxed_warning": 3,
        "warnings_and_cautions": 3,
        "drug_interactions": None, # тяжесть из контекста
    }

    found: dict[str, int] = {}  # drug_name → max severity

    for section, base_severity in sections.items():
        text = " ".join(label.get(section, [])).lower()
        if not text:
            continue

        for drug_name, drug_class in target_drugs.items():
            if drug_name not in text:
                continue

            # Если препарат в contraindications — сразу severity 4
            if base_severity == 4:
                severity = 4
            elif base_severity is not None:
                # Ищем контекст вокруг упоминания
                idx = text.find(drug_name)
                context = text[max(0, idx - WINDOW):idx + WINDOW]
                severity = max(base_severity, _classify_severity(context))
            else:
                idx = text.find(drug_name)
                context = text[max(0, idx - WINDOW):idx + WINDOW]
                severity = _classify_severity(context)

            if drug_name not in found or found[drug_name] < severity:
                found[drug_name] = severity

    return [{"target": name, "severity": sev} for name, sev in found.items()]


def collect_and_save():
    drug_names = {name: cls for name, (_, cls) in DRUG_REGISTRY.items()}
    name_to_class = {name: cls for name, (_, cls) in DRUG_REGISTRY.items()}

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    raw_path   = out_dir / "drug_interactions_raw.csv"
    class_path = out_dir / "class_pairs_real.csv"

    raw_rows: list[dict] = []

    print(f"Загружаю FDA-инструкции для {len(DRUG_REGISTRY)} препаратов...\n")

    for i, (drug_name, (fda_name, drug_class)) in enumerate(DRUG_REGISTRY.items(), 1):
        label = _fetch_label(fda_name)
        if label is None:
            print(f"  [{i:2d}/{len(DRUG_REGISTRY)}] {drug_name:<22} — инструкция не найдена")
            time.sleep(0.3)
            continue

        # Ищем все другие препараты кроме самого себя
        other_drugs = {n: c for n, (_, c) in DRUG_REGISTRY.items() if n != drug_name}
        interactions = _extract_interactions(label, other_drugs)

        for inter in interactions:
            raw_rows.append({
                "drug1":    drug_name,
                "class1":   drug_class,
                "drug2":    inter["target"],
                "class2":   name_to_class[inter["target"]],
                "severity": inter["severity"],
                "source":   "FDA label (openFDA)",
            })

        print(f"  [{i:2d}/{len(DRUG_REGISTRY)}] {drug_name:<22} → {len(interactions)} взаимодействий")
        time.sleep(0.3)

    # Дедупликация: одна пара может встретиться в инструкции обоих препаратов
    dedup: dict[tuple[str, str], dict] = {}
    for row in raw_rows:
        key = tuple(sorted([row["drug1"], row["drug2"]]))
        if key not in dedup or dedup[key]["severity"] < row["severity"]:
            dedup[key] = row

    dedup_rows = list(dedup.values())
    print(f"\nУникальных лекарственных пар: {len(dedup_rows)}")

    with open(raw_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["drug1", "class1", "drug2", "class2", "severity", "source"])
        w.writeheader()
        w.writerows(dedup_rows)

    # Агрегация по классам — берём максимальную тяжесть для пары классов
    class_pairs: dict[tuple[str, str], int] = {}
    for row in dedup_rows:
        key = tuple(sorted([row["class1"], row["class2"]]))
        sev = row["severity"]
        if key not in class_pairs or class_pairs[key] < sev:
            class_pairs[key] = sev

    print(f"Уникальных пар фармакологических классов: {len(class_pairs)}")

    with open(class_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["class_a", "class_b", "severity"])
        w.writeheader()
        for (ca, cb), sev in sorted(class_pairs.items()):
            w.writerow({"class_a": ca, "class_b": cb, "severity": sev})

    print(f"\nСохранено:")
    print(f"  {raw_path}")
    print(f"  {class_path}")

    from collections import Counter
    labels = {1: "mild", 2: "moderate", 3: "severe", 4: "contraindicated"}
    print("\nРаспределение по тяжести (классы):")
    for sev, cnt in sorted(Counter(class_pairs.values()).items()):
        print(f"  {sev} ({labels[sev]}): {cnt} пар")


if __name__ == "__main__":
    collect_and_save()
