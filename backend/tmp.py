import pandas as pd
import re
import requests
import time

# =========================
# 1. Wczytanie datasetu
# =========================

df = pd.read_csv("twcs.csv")

print("Liczba rekordów:", len(df))

# tylko wiadomości klientów
df = df[df["inbound"] == True]
df = df[df["text"].notna()]

print("Po filtrze inbound:", len(df))

# =========================
# 2. Czyszczenie tekstu
# =========================

def clean_text(text):
    text = str(text)
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

df["clean_text"] = df["text"].apply(clean_text)

df = df[df["clean_text"].str.len() > 15]

# =========================
# 3. Sample 500 rekordów
# =========================

df_sample = df.sample(500, random_state=42).copy()

# =========================
# 4. Prompt do Ollamy
# =========================

CATEGORIES = """
- complaint (skarga klienta)
- refund (zwrot pieniędzy)
- technical_issue (problem techniczny)
- account_issue (logowanie / konto)
- order_status (status zamówienia / paczki)
- spam (spam / nieistotne)
- other (inne pytania)
"""

def classify_with_ollama(text):
    prompt = f"""
You are a strict customer support text classifier.

Classify the message into EXACTLY ONE category:

{CATEGORIES}

Return ONLY the label, nothing else.

Message:
\"\"\"{text}\"\"\"
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.1:8b",
            "prompt": prompt,
            "stream": False
        }
    )

    result = response.json()["response"].strip().lower()

    # fallback sanity check
    valid_labels = [
        "complaint",
        "refund",
        "technical_issue",
        "account_issue",
        "order_status",
        "spam",
        "other"
    ]

    for label in valid_labels:
        if label in result:
            return label

    return "other"

# =========================
# 5. Labelowanie
# =========================

labels = []

for i, row in enumerate(df_sample["clean_text"]):
    try:
        label = classify_with_ollama(row)
        labels.append(label)

        print(f"[{i+1}/500] {label} | {row[:60]}")

        time.sleep(0.2)  # lekkie throttling

    except Exception as e:
        print("Błąd:", e)
        labels.append("other")

df_sample["label"] = labels

# =========================
# 6. Zapis wyniku
# =========================

df_sample.to_csv("twcs_labeled.csv", index=False)

print("\nZapisano: twcs_labeled_500.csv")

# =========================
# 7. Podsumowanie klas
# =========================

print("\n===== PODSUMOWANIE KLAS =====\n")

class_counts = df_sample["label"].value_counts()

print(class_counts)

print("\n===== PROCENTOWY ROZKŁAD =====\n")

class_percent = df_sample["label"].value_counts(normalize=True) * 100
print(class_percent.round(2))

# =========================
# 8. Ładna tabela (opcjonalnie)
# =========================

summary_df = pd.DataFrame({
    "count": class_counts,
    "percent": class_percent.round(2)
})

print("\n===== TABELA PODSUMOWUJĄCA =====\n")
print(summary_df)

# =========================
# 9. Zapis statystyk
# =========================

summary_df.to_csv("class_distribution.csv")

print("\nZapisano: class_distribution.csv")