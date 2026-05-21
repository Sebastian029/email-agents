import os
import django
import csv
import re
from typing import Callable, Tuple, List, Dict

from collections import Counter, defaultdict

# =========================
#  KONFIGURACJA DJANGO
# =========================

# Ustaw IDENTYCZNIE jak w manage.py
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "DjangoProject.settings")
django.setup()

from emails.tasks import query_ollama


# =========================
#  WSPÓLNE DEFINICJE
# =========================

LABELS = [
    "complaint",
    "refund",
    "technical_issue",
    "account_issue",
    "order_status",
    "spam",
    "other",
]

CATEGORIES_DESCRIPTION = """
- complaint (skarga klienta)
- refund (zwrot pieniędzy)
- technical_issue (problem techniczny)
- account_issue (logowanie / konto)
- order_status (status zamówienia / paczki)
- spam (spam / nieistotne)
- other (inne pytania)
"""

# MODELE DO TESTÓW
MODELS = [
    "gemma3:1b",
    "phi3:3.8b",
    "llama3.1:8b",
]

# Maksymalna liczba przykładów z CSV na jedną kombinację (model × prompt)
MAX_SAMPLES_PER_COMBO = 10


ClassifierFn = Callable[[str, str], Tuple[str, int]]
# (text, model_name) -> (category, priority)


def _call_llm(prompt: str, model: str) -> str:
    """
    Mały wrapper na query_ollama, żeby przekazać nazwę modelu.
    """
    return query_ollama(prompt, model=model).strip()


def _parse_category_priority(raw_response: str) -> Tuple[str, int]:
    """
    Wspólne parsowanie odpowiedzi typu:
    'complaint | 8', 'KATEGORIA: refund | priorytet=7' itd.
    Zwraca (category, priority).
    """
    clean = re.sub(r"<think>.*?</think>", "", raw_response, flags=re.DOTALL).strip()
    clean = clean.replace("*", "").replace("`", "").strip()

    parts = clean.split("|")

    category = "other"
    priority = 5

    if len(parts) >= 2:
        cat_part = parts[0].strip().lower()
        for label in LABELS:
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


# =========================
#  3 POZIOMY PROMPTU
# =========================

def classify_simple(text: str, model: str) -> Tuple[str, int]:
    """
    Podstawowy, najprostszy prompt.
    """
    prompt = f"""
Masz zaklasyfikować poniższy e-mail klienta do jednej z kategorii oraz ocenić priorytet.

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
Jesteś asystentem działu obsługi klienta.

Twoje zadanie:
1. Przeczytaj treść e-maila.
2. Zastanów się, jaki jest główny temat wiadomości.
3. Wybierz NAJBARDZIEJ pasującą kategorię z listy.
4. Oceń priorytet sprawy w skali 1–10 (10 = bardzo pilne).

Kategorie:
{CATEGORIES_DESCRIPTION}

Zwróć TYLKO wynik w formacie:
KATEGORIA | PRIORYTET

Przykład:
complaint | 9

Treść wiadomości:
{text[:2000]}
"""
    raw = _call_llm(prompt, model)
    return _parse_category_priority(raw)


def classify_detailed(text: str, model: str) -> Tuple[str, int]:
    """
    Szczegółowy prompt z dokładnym opisem każdej kategorii i priorytetu.
    """
    prompt = f"""
Jesteś ekspertem ds. obsługi klienta w dużej firmie e-commerce.

Twoim zadaniem jest:
- przypisać e-mail klienta do jednej z kategorii wsparcia,
- określić pilność sprawy w skali 1–10.

Kategorie i ich znaczenie:
- complaint       (skarga klienta: niezadowolenie, groźba rezygnacji, żądanie interwencji)
- refund          (prośba o zwrot pieniędzy, korekta płatności, chargeback)
- technical_issue (problem techniczny z produktem, stroną, aplikacją, logowaniem)
- account_issue   (problem z kontem klienta: dane, logowanie, blokada, zmiana hasła)
- order_status    (pytania o status zamówienia, numer śledzenia, dostawę)
- spam            (spam, reklama niezwiązana z obsługą klienta, treści bez znaczenia)
- other           (wszystko inne: ogólne pytania, sugestie, informacje)

Priorytet:
- 10: bardzo pilne (groźba zgłoszenia do instytucji, duża szkoda dla klienta, poważny błąd)
- 7–9: ważne problemy (produkt nie działa, klient nie może korzystać z usługi, problemy z płatnością)
- 4–6: normalne sprawy (pytania o zamówienie, fakturę, konfigurację)
- 1–3: mało pilne (spam, oferty, ciekawostki, drobne uwagi)

Instrukcja:
1. Przeanalizuj treść e-maila.
2. Wybierz dokładnie jedną kategorię z listy (nazwę w formie: complaint, refund, itd.).
3. Ustal liczbę od 1 do 10 zgodnie z powyższym opisem pilności.
4. NIE pisz wyjaśnienia, NIE dodawaj komentarza.

Zwróć TYLKO:
KATEGORIA | PRIORYTET

Treść wiadomości:
{text[:2000]}
"""
    raw = _call_llm(prompt, model)
    return _parse_category_priority(raw)


PROMPT_VARIANTS: Dict[str, ClassifierFn] = {
    "simple": classify_simple,
    "medium": classify_medium,
    "detailed": classify_detailed,
}


# =========================
#  METRYKI KLASYFIKACJI
# =========================

def compute_basic_metrics(
    true_labels: List[str],
    pred_labels: List[str],
    labels: List[str],
) -> Dict[str, float]:
    """
    Liczy:
    - accuracy
    - macro precision
    - macro recall
    - macro F1

    Bez sklearn, „ręcznie”, na potrzeby csv.
    """
    assert len(true_labels) == len(pred_labels)
    n = len(true_labels)

    # Accuracy
    correct = sum(1 for t, p in zip(true_labels, pred_labels) if t == p)
    accuracy = correct / n if n > 0 else 0.0

    # Confusion counts per label
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


# =========================
#  GŁÓWNY SILNIK: GRID (MODEL × PROMPT)
# =========================

def run_grid(csv_path: str, max_samples: int = MAX_SAMPLES_PER_COMBO):
    """
    Dla każdej kombinacji (model × prompt_variant):
    - bierze do max_samples przykładów z CSV,
    - uruchamia klasyfikację,
    - liczy metryki,
    - zapisuje szczegółowe wyniki + podsumowanie do CSV.
    """

    # Wczytanie całego CSV raz
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    # Plik wynikowy (połączony)
    output_file = "llm_grid_results.csv"

    # Przygotuj nagłówek CSV
    header = [
        "model",
        "prompt_variant",
        "row_index",
        "true_label",
        "predicted_label",
        "priority",
        "sample_text",   # możesz potem uciąć przy analizie
        "accuracy",
        "macro_precision",
        "macro_recall",
        "macro_f1",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.writer(out_f)
        writer.writerow(header)

        # Dla każdej kombinacji model × prompt_variant
        for model_name in MODELS:
            for variant_name, fn in PROMPT_VARIANTS.items():
                print(f"\n=== MODEL: {model_name} | PROMPT: {variant_name} ===")

                true_labels: List[str] = []
                pred_labels: List[str] = []
                priorities: List[int] = []

                # iterujemy po wierszach CSV, ale ucinamy do max_samples na kombinację
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

                    # metryki policzymy po pętli, tutaj accuracy* itd. na razie puste
                    writer.writerow([
                        model_name,
                        variant_name,
                        idx,
                        true_label,
                        pred_label,
                        priority,
                        text[:200],  # sample_text skrócony
                        "", "", "", "",
                    ])

                    print(f"[{model_name}/{variant_name}][{idx+1}] TRUE: {true_label:15} | PRED: {pred_label:15} | prio={priority}")

                # Po przejściu próbek dla tej kombinacji liczymy metryki
                metrics = compute_basic_metrics(true_labels, pred_labels, LABELS)
                print(
                    f"SUMMARY {model_name}/{variant_name}: "
                    f"acc={metrics['accuracy']:.3f}, "
                    f"P={metrics['macro_precision']:.3f}, "
                    f"R={metrics['macro_recall']:.3f}, "
                    f"F1={metrics['macro_f1']:.3f}"
                )

                # Dopisujemy specjalny wiersz-podsumowanie (row_index = -1)
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
    CSV_PATH = "twcs_labeled.csv"

    run_grid(CSV_PATH, max_samples=MAX_SAMPLES_PER_COMBO)
    print("\nWyniki zapisane w pliku: llm_grid_results.csv")