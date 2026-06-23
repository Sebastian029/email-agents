import time
import csv
import re
import pandas as pd
import ollama
import itertools
from tqdm import tqdm

from dataset_config import CATEGORIES_DESCRIPTION, DEFAULT_LABEL, NEWSGROUP_LABELS


OUTPUT_CSV = "prompt_timing_summary.csv"

MODELS = [
    "gemma3:1b",
    "phi3:3.8b",
    "llama3.1:8b"
]

N_RUNS = 50


LABELS = NEWSGROUP_LABELS
CATEGORIES = ", ".join(NEWSGROUP_LABELS)

def parse_category_priority(raw_response: str):
    clean = re.sub(r"<think>.*?</think>", "", raw_response, flags=re.DOTALL).strip()
    clean = clean.replace("|", "\n").replace(",", "\n").strip()
    parts = clean.split("\n")

    category = DEFAULT_LABEL
    priority = 5

    if len(parts) >= 1:
        cat_part = parts[0].strip().lower()

        for label in sorted(LABELS, key=len, reverse=True):
            if label in cat_part:
                category = label
                break

        try:
            if len(parts) >= 2:
                nums = re.findall(r"\d+", parts[1])
                if nums:
                    priority = int(nums[0])
        except Exception:
            priority = 5

    return category, priority

PROMPTS = {
    "P1_ZeroShot": (
        f"Sklasyfikuj poniższą wiadomość do jednej z kategorii: {CATEGORIES}. "
        f"Odpowiedz TYLKO nazwą kategorii.\n\nWiadomość:\n"
    ),
    "P2_ZeroShot_EN": (
        f"Classify the following message into one of these categories: {CATEGORIES}. "
        f"Reply with ONLY the category name.\n\nMessage:\n"
    ),
    "P3_Persona": (
        f"Jesteś wybitnym analitykiem danych. Twoim jedynym zadaniem jest precyzyjna "
        f"klasyfikacja tekstów. Wybierz jedną z kategorii: {CATEGORIES} dla poniższej "
        f"wiadomości. Odpowiedz wyłącznie nazwą kategorii.\n\nWiadomość:\n"
    ),
    "P4_FewShot": (
        f"Sklasyfikuj wiadomość do kategorii: {CATEGORIES}.\n"
        f"Przykład 1: 'Szukam części do silnika, ktoś poleca warsztat?' -> rec.autos\n"
        f"Przykład 2: 'Teleskop Hubble wykonał zdjęcie nowej mgławicy' -> sci.space\n"
        f"Przykład 3: 'Czy PNG obsługuje przezroczystość lepiej niż JPEG?' -> comp.graphics\n"
        f"Przykład 4: 'Sprzedam monitor w dobrym stanie, cena do negocjacji' -> misc.forsale\n"
        f"Przykład 5: 'Jakie są objawy niedoboru witaminy D?' -> sci.med\n"
        f"Teraz Twoja kolej. Odpowiedz tylko nazwą kategorii.\n\nWiadomość:\n"
    ),
}

def run_prompt_timing():
    combinations = list(itertools.product(MODELS, PROMPTS.items()))

    summary_results = []

    for model_name, (prompt_name, prompt_template) in combinations:

        times_for_summary = []

        for run_idx in tqdm(range(1, N_RUNS + 1), desc=f"{model_name} | {prompt_name}"):
            full_prompt = prompt_template + f"\n\n[ID: {run_idx}]"

            try:
                start = time.time()

                response = ollama.generate(
                    model=model_name,
                    prompt=full_prompt,
                    options={
                        "temperature": 0.1,
                        "num_predict": 1000,
                    }
                )

                elapsed_ms = (time.time() - start) * 1000
                raw_response = response["response"].strip()


                times_for_summary.append(elapsed_ms)

            except Exception as e:
                print(f"{model_name}: {e}")

        if times_for_summary:
            avg_time = sum(times_for_summary) / len(times_for_summary)


            summary_results.append({
                "model": model_name,
                "prompt_type": prompt_name,
                "srednia_czas_odpowiedzi_ms": round(avg_time, 2)
            })
        else:
            print("Blad")

    if summary_results:
        df = pd.DataFrame(summary_results)
        df.to_csv(OUTPUT_CSV, index=False)
    else:
        print("Brak danych")


if __name__ == "__main__":
    run_prompt_timing()