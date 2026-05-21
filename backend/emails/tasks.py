from django.utils import timezone
import requests
import re

from .models import EmailMessage
from django_q.tasks import async_task

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


def query_ollama(prompt, model="gemma3:1b"):
    """
    Niski poziom: wywołanie lokalnego modelu przez API Ollama.
    Zwraca surową odpowiedź modelu jako string (lub komunikat błędu).
    """
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
            },
            timeout=600,
        )
        data = response.json()
        # Standardowo Ollama używa pola "response" na tekst modelu
        return data.get("response", "")
    except Exception as e:
        return f"Error connecting to Ollama: {str(e)}"


# =========================
#  WSPÓLNY „MÓZG” KLASIFIKACJI
# =========================

# Kategorie używane w systemie produkcyjnym (agent_classify_email)
PROD_LABELS = [
    "complaint",
    "refund",
    "technical_issue",
    "account_issue",
    "order_status",
    "spam",
    "other",
]

def classify_email_text(text: str) -> tuple[str, int]:
    """
    Czysta funkcja klasyfikująca treść maila.
    Teraz używa kategorii:
    [complaint, refund, technical_issue, account_issue, order_status, spam, other].

    Zwraca:
    - category: string z nazwą kategorii (np. 'complaint')
    - priority: int 1–10 (nadal liczony, jeśli chcesz go używać)
    """

    prompt = f"""
Jesteś asystentem do klasyfikacji wiadomości e-mail w systemie obsługi klienta.

Masz do dyspozycji następujące kategorie (podaj NAZWĘ KATEGORII dokładnie jak poniżej):
- complaint       (skarga klienta)
- refund          (zwrot pieniędzy)
- technical_issue (problem techniczny)
- account_issue   (logowanie / konto)
- order_status    (status zamówienia / paczki)
- spam            (spam / nieistotne)
- other           (inne pytania)

Przeanalizuj treść wiadomości poniżej i zwróć TYLKO:
KATEGORIA | PRIORYTET

gdzie:
- KATEGORIA to jedna z powyższych nazw (np. complaint, refund, technical_issue)
- PRIORYTET to liczba od 1 do 10 (10 = najważniejsze)

Treść wiadomości:
{text[:2000]}
"""

    raw_response = query_ollama(prompt).strip()

    # Usuwamy ewentualne <think>...</think> i dziwne znaki
    clean_response = re.sub(
        r"<think>.*?</think>",
        "",
        raw_response,
        flags=re.DOTALL,
    ).strip()
    clean_response = clean_response.replace("*", "").replace("`", "")

    parts = clean_response.split("|")

    # Domyślne wartości
    category = "other"
    priority = 5

    if len(parts) >= 2:
        # Kategoria (po lewej stronie)
        cat = parts[0].strip()
        cat_lower = cat.lower()

        # Spróbuj dopasować do znanych etykiet
        for label in PROD_LABELS:
            if label in cat_lower:
                category = label
                break
        else:
            # jeśli model coś dziwnego zwróci, zostaw domyślne "other"
            pass

        # Priorytet – pierwsza liczba w drugiej części
        try:
            prio_str = parts[1].strip()
            nums = re.findall(r"\d+", prio_str)
            if nums:
                priority = int(nums[0])
        except Exception:
            priority = 5
    else:
        # Jeśli odpowiedź nie ma formatu "KATEGORIA | PRIORYTET",
        # zostają domyślne: other, 5
        pass

    return category, priority

# =========================
#  AGENT 1: Classifier
# =========================

def agent_classify_email(email_id=None):
    if not email_id:
        return None

    try:
        email = EmailMessage.objects.get(id=email_id)
        print(f"🕵️ [Classifier] Analizuję maila ID: {email.id} | Temat: {email.subject}")

        tresc_maila = email.body_text if email.body_text else email.body_html

        # Używamy wspólnej funkcji „mózgu”
        category, priority = classify_email_text(tresc_maila)

        email.category = category
        email.priority_score = priority
        email.save()

        print(f"✅ [Classifier] Wynik: {category} (Priorytet: {priority})")

        # Idziemy dalej niezależnie od wyniku
        async_task('emails.tasks.agent_summarize_email', email.id)
        return email.id

    except Exception as e:
        print(f"❌ [Classifier] Błąd: {str(e)}")
        async_task('emails.tasks.agent_summarize_email', email_id)
        return None


# =========================
#  AGENT 2: Summarizer
# =========================

def agent_summarize_email(email_id=None):
    if not email_id:
        return None

    try:
        email = EmailMessage.objects.get(id=email_id)

        if email.category == "SPAM":
            print(f"🛑 [Summarizer] Pomijam SPAM (ID: {email.id})")
            return email.id

        print(f"🧠 [Summarizer] Streszczam maila ID: {email.id}")
        tresc_maila = email.body_text if email.body_text else email.body_html

        prompt = f"""
        Zrób zwięzłe streszczenie tego e-maila w 2-3 zdaniach po polsku.
        Najważniejsze informacje: kto, co chce, do kiedy.
        Temat: {email.subject}
        Treść: {tresc_maila[:2000]}
        """

        raw_response = query_ollama(prompt)
        summary = re.sub(
            r"<think>.*?</think>",
            "",
            raw_response,
            flags=re.DOTALL,
        ).strip()

        email.ai_summary = summary
        email.save()
        print(f"✅ [Summarizer] Gotowe.")

        async_task('emails.tasks.agent_draft_reply', email.id)
        return email.id

    except Exception as e:
        print(f"❌ [Summarizer] Błąd: {str(e)}")
        async_task('emails.tasks.agent_draft_reply', email_id)
        return None


# =========================
#  AGENT 3: Drafter
# =========================

def agent_draft_reply(email_id=None):
    if not email_id:
        return None

    try:
        email = EmailMessage.objects.get(id=email_id)

        if email.category == "SPAM":
            print(f"🛑 [Drafter] Pomijam SPAM (ID: {email.id})")
            email.processed = True
            email.save()
            return email.id

        print(f"✍️ [Drafter] Piszę odpowiedź dla ID: {email.id}")

        prompt = f"""
Przygotuj uprzejmą propozycję odpowiedzi na tego maila w języku polskim.
Kontekst: Mail kategorii {email.category}. Streszczenie: {email.ai_summary}
Wiadomość od: {email.sender}. Temat: {email.subject}
Napisz samą treść odpowiedzi bez wstępów.
"""

        raw_response = query_ollama(prompt)
        draft = re.sub(
            r"<think>.*?</think>",
            "",
            raw_response,
            flags=re.DOTALL,
        ).strip()

        email.ai_draft_reply = draft
        email.processed = True
        email.processed_at = timezone.now()
        email.save()

        print(f"✅ [Drafter] Odpowiedź gotowa. Koniec procesu dla ID: {email.id}.")
        return email.id

    except Exception as e:
        print(f"❌ [Drafter] Błąd: {str(e)}")
        return None