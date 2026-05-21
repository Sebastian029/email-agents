# Email Agents — Frontend

React + Vite + Tailwind CSS. Łączy się z Django API (`/api`).

## Uruchomienie

1. Backend Django na `http://127.0.0.1:8000` (migracje, użytkownik, django-q worker dla AI).
2. W tym katalogu:

```bash
npm install
npm run dev
```

Aplikacja: http://localhost:5173 — żądania `/api/*` są proxyowane do backendu.

## Funkcje

- Logowanie / rejestracja (JWT)
- Dodawanie skrzynek IMAP/SMTP
- Pobieranie maili z serwera
- Przeglądanie wg kategorii AI (skarga, zwrot, techniczne, …)
- Streszczenie, draft odpowiedzi, wysyłka SMTP
