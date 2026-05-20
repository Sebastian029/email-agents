from django.utils import timezone
import requests
import re
from .models import EmailMessage
from django_q.tasks import async_task

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


# Zmienione na mały i szybki model (upewnij się że masz go w Ollamie)
def query_ollama(prompt, model="gemma3:1b"):
    try:
        response = requests.post(OLLAMA_URL, json={
            "model": model,
            "prompt": prompt,
            "stream": False
        }, timeout=600)
        return response.json().get("response", "")
    except Exception as e:
        return f"Error connecting to Ollama: {str(e)}"


# --- AGENT 1: Classifier ---
def agent_classify_email(email_id=None):
    if not email_id:
        return None
    try:
        email = EmailMessage.objects.get(id=email_id)
        print(f"🕵️ [Classifier] Analizuję maila ID: {email.id} | Temat: {email.subject}")

        tresc_maila = email.body_text if email.body_text else email.body_html

        prompt = f"""
        Jesteś asystentem mailowym. Przeanalizuj poniższy e-mail i zaklasyfikuj go do jednej z kategorii:
        [FAKTURA, OFERTA, REKLAMACJA, PRYWATNE, SPAM, INNE].
        Oceń też priorytet od 1 do 10 (10 = najważniejsze).
        Zwróć odpowiedź TYLKO w formacie: KATEGORIA | PRIORYTET

        Temat: {email.subject}
        Treść: {tresc_maila[:1000]}
        """

        raw_response = query_ollama(prompt).strip()
        clean_response = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL).strip()
        clean_response = clean_response.replace('*', '').replace('`', '')
        parts = clean_response.split('|')

        if len(parts) >= 2:
            category = parts[0].strip()[:99]
            try:
                priority = int(re.findall(r'\d+', parts[1].strip())[0])
            except:
                priority = 5

            email.category = category
            email.priority_score = priority
            email.save()
            print(f"✅ [Classifier] Wynik: {category} (Priorytet: {priority})")
        else:
            print(f"⚠️ [Classifier] Nie zrozumiałem formatu, wynik: {clean_response[:30]}")
            email.category = "UNKNOWN"
            email.save()

        # Idziemy dalej niezależnie od wyniku
        async_task('emails.tasks.agent_summarize_email', email.id)
        return email.id

    except Exception as e:
        print(f"❌ [Classifier] Błąd: {str(e)}")
        async_task('emails.tasks.agent_summarize_email', email_id)
        return None


# --- AGENT 2: Summarizer ---
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
        summary = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL).strip()
        email.ai_summary = summary
        email.save()
        print(f"✅ [Summarizer] Gotowe.")

        async_task('emails.tasks.agent_draft_reply', email.id)
        return email.id

    except Exception as e:
        print(f"❌ [Summarizer] Błąd: {str(e)}")
        async_task('emails.tasks.agent_draft_reply', email_id)
        return None


# --- AGENT 3: Drafter ---
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
        draft = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL).strip()
        email.ai_draft_reply = draft
        email.processed = True
        email.processed_at = timezone.now()
        email.save()
        print(f"✅ [Drafter] Odpowiedź gotowa. Koniec procesu dla ID: {email.id}.")
        return email.id

    except Exception as e:
        print(f"❌ [Drafter] Błąd: {str(e)}")
        return None