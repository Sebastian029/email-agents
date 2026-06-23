import time
import pandas as pd
import ollama
import itertools
from tqdm import tqdm


INPUT_CSV    = "test_data.csv"
OUTPUT_CSV   = "prompt_timing_results.csv"
LABEL_COLUMN = "label"
TEXT_COLUMN  = "clean_text"
N_RUNS       = 10

MODELS = [
    "phi3:3.8b",
    "llama3.1:8b",
    "gemma3:1b",
    "phi-tuned",
    "llama-tuned",
    "gemma-tuned",
]

CATEGORIES = "rec.autos, sci.space, comp.graphics, misc.forsale, sci.med"

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


def run_timing():
    df = pd.read_csv(INPUT_CSV)
    sample_text = str(df[TEXT_COLUMN].iloc[0])[:1500]

    columns = ["model", "prompt_type", "run_index", "response_time_ms", "predicted"]
    pd.DataFrame(columns=columns).to_csv(OUTPUT_CSV, index=False)

    combinations = list(itertools.product(MODELS, PROMPTS.items()))
    print(f"Konfiguracji: {len(combinations)} | Wywołań na konfigurację: {N_RUNS}")

    for model_name, (prompt_name, prompt_template) in combinations:
        print(f"\n[{model_name}] [{prompt_name}]")
        times = []

        for run_idx in tqdm(range(1, N_RUNS + 1), desc=f"{model_name}|{prompt_name}"):
            full_prompt = prompt_template + sample_text

            try:
                start = time.time()
                response = ollama.generate(
                    model=model_name,
                    prompt=full_prompt,
                    options={"temperature": 0.1, "num_predict": 50},
                )
                elapsed_ms = (time.time() - start) * 1000
                predicted = response["response"].strip()
            except Exception as e:
                elapsed_ms = -1
                predicted = "ERROR"
                print(f"  Błąd: {e}")

            times.append(elapsed_ms)
            pd.DataFrame([{
                "model":           model_name,
                "prompt_type":     prompt_name,
                "run_index":       run_idx,
                "response_time_ms": round(elapsed_ms, 2),
                "predicted":       predicted,
            }]).to_csv(OUTPUT_CSV, mode="a", header=False, index=False)

        valid = [t for t in times if t >= 0]
        if valid:
            print(f"  avg={sum(valid)/len(valid):.0f}ms  min={min(valid):.0f}ms  max={max(valid):.0f}ms")



if __name__ == "__main__":
    run_timing()