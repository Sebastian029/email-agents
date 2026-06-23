
import re

import pandas as pd
from sklearn.datasets import fetch_20newsgroups

from dataset_config import NEWSGROUP_LABELS

LABELED_CSV = "newsgroups_labeled.csv"
DISTRIBUTION_CSV = "class_distribution.csv"
SAMPLE_SIZE = 500
RANDOM_STATE = 42


def clean_text(text: str) -> str:
    text = str(text)
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_newsgroups_subset():
    data = fetch_20newsgroups(
        subset="all",
        categories=NEWSGROUP_LABELS,
        remove=("headers", "footers", "quotes"),
        shuffle=True,
        random_state=RANDOM_STATE,
    )
    rows = []
    for text, target in zip(data.data, data.target):
        label = data.target_names[target]
        cleaned = clean_text(text)
        if len(cleaned) > 15:
            rows.append({"clean_text": cleaned, "label": label})
    return pd.DataFrame(rows)


def main():
    df = load_newsgroups_subset()
    samples = []
    for label, group in df.groupby("label"):
        sampled_group = group.sample(min(len(group), 500), random_state=RANDOM_STATE)
        samples.append(sampled_group)

    df_sample = pd.concat(samples).reset_index(drop=True)


    print("Dostępne kolumny:", df_sample.columns.tolist())

    df_sample.to_csv(LABELED_CSV, index=False)
    print(f"\nZapisano: {LABELED_CSV} ({len(df_sample)} wierszy)")

    print("\n===== PODSUMOWANIE KLAS =====\n")
    class_counts = df_sample["label"].value_counts()
    print(class_counts)

    print("\n===== PROCENTOWY ROZKŁAD =====\n")
    class_percent = df_sample["label"].value_counts(normalize=True) * 100
    print(class_percent.round(2))

    summary_df = pd.DataFrame({
        "count": class_counts,
        "percent": class_percent.round(2),
    })
    print("\n===== TABELA PODSUMOWUJĄCA =====\n")
    print(summary_df)

    summary_df.to_csv(DISTRIBUTION_CSV)
    print(f"\nZapisano: {DISTRIBUTION_CSV}")


if __name__ == "__main__":
    main()
