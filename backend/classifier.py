import csv
import os
import django

# --- konfiguracja Django, żeby korzystać z tego samego kodu co projekt ---

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "DjangoProject.settings")
django.setup()

from emails.tasks import classify_email_text  # UWAGA: dostosuj nazwę projektu/appki


def evaluate_from_csv(csv_path: str, limit: int | None = None):
    """
    Czyta plik CSV z kolumnami clean_text, label
    i liczy accuracy klasyfikatora opartego na classify_email_text().
    """
    total = 0
    correct = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row["clean_text"]
            true_label = row["label"].strip().lower()

            category, priority = classify_email_text(text)
            predicted_label = category.lower()

            is_correct = (predicted_label == true_label)

            total += 1
            if is_correct:
                correct += 1

            print(f"[{total}] TRUE: {true_label:15} | PRED: {predicted_label:15} | prio={priority}")

            if limit is not None and total >= limit:
                break

    accuracy = (correct / total) if total > 0 else 0.0

    print("\n====================")
    print(f"Total samples: {total}")
    print(f"Correct:       {correct}")
    print(f"Accuracy:      {accuracy:.3f}")


if __name__ == "__main__":
    csv_file = "newsgroups_labeled.csv"
    evaluate_from_csv(csv_file, limit=50)