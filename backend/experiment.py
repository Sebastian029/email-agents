import os
import django
import csv
import re
from typing import Callable, Tuple, List, Dict

from collections import Counter, defaultdict


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "DjangoProject.settings")
django.setup()

from emails.tasks import query_ollama
from dataset_config import CATEGORIES_DESCRIPTION, DEFAULT_LABEL, NEWSGROUP_LABELS


LABELS = NEWSGROUP_LABELS

MODELS = [
    "gemma3:1b",
    "phi3:3.8b",
    "llama3.1:8b",
]

MAX_SAMPLES_PER_COMBO = 10


ClassifierFn = Callable[[str, str], Tuple[str, int]]


def _call_llm(prompt: str, model: str) -> str:
    return query_ollama(prompt, model=model).strip()


def _parse_category_priority(raw_response: str) -> Tuple[str, int]:
    clean = re.sub(r"<think>.*?</think>", "", raw_response, flags=re.DOTALL).strip()
    clean = clean.replace("*", "").replace("`", "").strip()

    parts = clean.split("|")

    category = DEFAULT_LABEL
    priority = 5

    if len(parts) >= 2:
        cat_part = parts[0].strip().lower()
        for label in sorted(LABELS, key=len, reverse=True):
            if label in cat_part:
                category = label
                break

        try:
            nums = re.findall(r"\d+", parts[1])
            if nums:
                priority = int(nums[0])
        except Exception:
            priority = 5

    return category, priority




def classify_simple(text: str, model: str) -> Tuple[str, int]:

    prompt = f"""
        Zaklasyfikuj poniższy post z grupy dyskusyjnej do jednej kategorii newsgroup oraz oceń priorytet.
        
        Kategorie (podaj nazwę dokładnie w takiej formie):
        {CATEGORIES_DESCRIPTION}
        
        Zwróć TYLKO:
        KATEGORIA | PRIORYTET
        
        Treść:
        {text[:2000]}
        """
    raw = _call_llm(prompt, model)
    return _parse_category_priority(raw)


def classify_medium(text: str, model: str) -> Tuple[str, int]:
    """
    Średnio rozbudowany prompt: trochę więcej opisu, ale nadal zwięzły.
    """
    prompt = f"""
    Jesteś klasyfikatorem postów z grup dyskusyjnych (20 Newsgroups).
    
    Twoje zadanie:
    1. Przeczytaj treść posta.
    2. Określ główny temat (sprzęt, system, grafika, elektronika).
    3. Wybierz NAJBARDZIEJ pasującą kategorię z listy.
    4. Oceń priorytet w skali 1–10 (10 = bardzo istotny / pilny wątek).
    
    Kategorie:
    {CATEGORIES_DESCRIPTION}
    
    Zwróć TYLKO wynik w formacie:
    KATEGORIA | PRIORYTET
    
    Przykład:
    comp.graphics | 7
    
    Treść:
    {text[:2000]}
    """
    raw = _call_llm(prompt, model)
    return _parse_category_priority(raw)


def classify_detailed(text: str, model: str) -> Tuple[str, int]:

    prompt = f"""
        Jesteś ekspertem od klasyfikacji postów w stylu 20 Newsgroups (tematyka IT i elektroniki).
        
        Twoim zadaniem jest:
        - przypisać post do jednej kategorii newsgroup,
        - określić pilność / istotność wątku w skali 1–10.
        
        Kategorie i ich znaczenie:
        {CATEGORIES_DESCRIPTION}
        
        Priorytet:
        - 10: krytyczny problem sprzętowy, awaria, pilna prośba o pomoc
        - 7–9: ważne pytanie techniczne, konfiguracja, porównanie sprzętu
        - 4–6: zwykła dyskusja, porada, recenzja
        - 1–3: luźna wymiana, off-topic w obrębie grupy
        
        Instrukcja:
        1. Przeanalizuj treść posta.
        2. Wybierz dokładnie jedną kategorię (np. comp.graphics, sci.electronics).
        3. Ustal liczbę od 1 do 10.
        4. NIE pisz wyjaśnienia.
        
        Zwróć TYLKO:
        KATEGORIA | PRIORYTET
        
        Treść:
        {text[:2000]}
        """
    raw = _call_llm(prompt, model)
    return _parse_category_priority(raw)


PROMPT_VARIANTS: Dict[str, ClassifierFn] = {
    "simple": classify_simple,
    "medium": classify_medium,
    "detailed": classify_detailed,
}



def compute_basic_metrics(
    true_labels: List[str],
    pred_labels: List[str],
    labels: List[str],
) -> Dict[str, float]:

    assert len(true_labels) == len(pred_labels)
    n = len(true_labels)

    correct = sum(1 for t, p in zip(true_labels, pred_labels) if t == p)
    accuracy = correct / n if n > 0 else 0.0

    tp = Counter()
    fp = Counter()
    fn = Counter()

    for t, p in zip(true_labels, pred_labels):
        if t == p:
            tp[t] += 1
        else:
            fp[p] += 1
            fn[t] += 1

    precisions = []
    recalls = []
    f1s = []

    for label in labels:
        tp_l = tp[label]
        fp_l = fp[label]
        fn_l = fn[label]

        prec = tp_l / (tp_l + fp_l) if (tp_l + fp_l) > 0 else 0.0
        rec = tp_l / (tp_l + fn_l) if (tp_l + fn_l) > 0 else 0.0
        if prec + rec > 0:
            f1 = 2 * prec * rec / (prec + rec)
        else:
            f1 = 0.0

        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)

    macro_precision = sum(precisions) / len(labels) if labels else 0.0
    macro_recall = sum(recalls) / len(labels) if labels else 0.0
    macro_f1 = sum(f1s) / len(labels) if labels else 0.0

    return {
        "accuracy": accuracy,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
    }


def run_grid(csv_path: str, max_samples: int = MAX_SAMPLES_PER_COMBO):
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    output_file = "llm_grid_results.csv"

    header = [
        "model",
        "prompt_variant",
        "row_index",
        "true_label",
        "predicted_label",
        "priority",
        "sample_text",
        "accuracy",
        "macro_precision",
        "macro_recall",
        "macro_f1",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.writer(out_f)
        writer.writerow(header)

        for model_name in MODELS:
            for variant_name, fn in PROMPT_VARIANTS.items():
                print(f"\n=== MODEL: {model_name} | PROMPT: {variant_name} ===")

                true_labels: List[str] = []
                pred_labels: List[str] = []
                priorities: List[int] = []

                for idx, row in enumerate(reader):
                    if idx >= max_samples:
                        break

                    text = row["clean_text"]
                    true_label = row["label"].strip().lower()

                    pred_label, priority = fn(text, model_name)
                    pred_label = pred_label.lower()

                    true_labels.append(true_label)
                    pred_labels.append(pred_label)
                    priorities.append(priority)

                    writer.writerow([
                        model_name,
                        variant_name,
                        idx,
                        true_label,
                        pred_label,
                        priority,
                        text[:200],
                        "", "", "", "",
                    ])

                    print(f"[{model_name}/{variant_name}][{idx+1}] TRUE: {true_label:15} | PRED: {pred_label:15} | prio={priority}")

                metrics = compute_basic_metrics(true_labels, pred_labels, LABELS)
                print(
                    f"SUMMARY {model_name}/{variant_name}: "
                    f"acc={metrics['accuracy']:.3f}, "
                    f"P={metrics['macro_precision']:.3f}, "
                    f"R={metrics['macro_recall']:.3f}, "
                    f"F1={metrics['macro_f1']:.3f}"
                )

                writer.writerow([
                    model_name,
                    variant_name,
                    -1,
                    "SUMMARY",
                    "",
                    "",
                    "",
                    metrics["accuracy"],
                    metrics["macro_precision"],
                    metrics["macro_recall"],
                    metrics["macro_f1"],
                ])


if __name__ == "__main__":
    CSV_PATH = "newsgroups_labeled.csv"

    run_grid(CSV_PATH, max_samples=MAX_SAMPLES_PER_COMBO)
    print("\nWyniki zapisane w pliku: llm_grid_results.csv")