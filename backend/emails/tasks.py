from django.utils import timezone
import requests
import re

from dataset_config import CATEGORIES_DESCRIPTION, DEFAULT_LABEL, NEWSGROUP_LABELS

from .models import EmailMessage
from django_q.tasks import async_task

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


def query_ollama(prompt, model="gemma3:1b"):
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
        return data.get("response", "")
    except Exception as e:
        return f"Error connecting to Ollama: {str(e)}"



PROD_LABELS = NEWSGROUP_LABELS


def classify_email_text(text: str) -> tuple[str, int]:
    prompt = f"""
        Jesteś klasyfikatorem postów 20 Newsgroups (IT / elektronika).
        
        Kategorie (podaj NAZWĘ dokładnie jak poniżej):
        {CATEGORIES_DESCRIPTION}
        
        Przeanalizuj treść poniżej i zwróć TYLKO:
        KATEGORIA | PRIORYTET
        
        gdzie KATEGORIA to jedna z powyższych nazw (np. comp.graphics, sci.electronics),
        a PRIORYTET to liczba 1–10.
        
        Treść:
        {text[:2000]}
        """

    raw_response = query_ollama(prompt).strip()

    clean_response = re.sub(
        r"<think>.*?</think>",
        "",
        raw_response,
        flags=re.DOTALL,
    ).strip()
    clean_response = clean_response.replace("*", "").replace("`", "")

    parts = clean_response.split("|")

    category = DEFAULT_LABEL
    priority = 5

    if len(parts) >= 2:
        cat_lower = parts[0].strip().lower()

        for label in sorted(PROD_LABELS, key=len, reverse=True):
            if label in cat_lower:
                category = label
                break

        try:
            prio_str = parts[1].strip()
            nums = re.findall(r"\d+", prio_str)
            if nums:
                priority = int(nums[0])
        except Exception:
            priority = 5
    else:
        pass

    return category, priority



def agent_classify_email(email_id=None):
    if not email_id:
        return None

    try:
        email = EmailMessage.objects.get(id=email_id)
        print(f"🕵️ [Classifier] Analizuję maila ID: {email.id} | Temat: {email.subject}")

        tresc_maila = email.body_text if email.body_text else email.body_html

        category, priority = classify_email_text(tresc_maila)

        email.category = category
        email.priority_score = priority
        email.save()

        print(f"✅ [Classifier] Wynik: {category} (Priorytet: {priority})")

        async_task('emails.tasks.agent_summarize_email', email.id)
        return email.id

    except Exception as e:
        print(f"❌ [Classifier] Błąd: {str(e)}")
        async_task('emails.tasks.agent_summarize_email', email_id)
        return None



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