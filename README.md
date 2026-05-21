# email-agents

System obsługi skrzynki e-mail z klasyfikacją AI (Ollama) — Django REST + React.

## Uruchomienie

### Backend

```bash
cd backend
docker compose -f ../docker-compose.yml up -d   # PostgreSQL
python manage.py migrate
python manage.py runserver
python manage.py qcluster   # worker AI (osobny terminal)
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

- API: http://127.0.0.1:8000
- UI: http://localhost:5173

Zarejestruj konto w UI, dodaj skrzynkę IMAP, kliknij **Pobierz z IMAP**. Kategorie i streszczenia pojawią się po przetworzeniu przez django-q + Ollama.