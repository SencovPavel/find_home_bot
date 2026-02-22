# Запуск Rental Bot

Краткая инструкция по запуску приложения в разных сценариях.

## Предварительные требования

- Python 3.9+
- Токен бота от [@BotFather](https://t.me/BotFather)
- Ваш Telegram user ID ([@userinfobot](https://t.me/userinfobot))

## 1. Минимальный запуск (только бот)

```bash
cd bot
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env
# Отредактируйте .env: BOT_TOKEN, ADMIN_USER_ID
python -m src.main
```

Успех: в логах «Бот запущен», «Планировщик запущен».

## 2. Запуск с Mini App (дашборд)

Mini App требует HTTPS. Для локальной разработки используйте ngrok.

1. Установите [ngrok](https://ngrok.com/)
2. В отдельном терминале: `ngrok http 8080`
3. Скопируйте HTTPS-URL (например `https://abc123.ngrok-free.app`) в `.env`:

   ```
   WEBAPP_URL=https://abc123.ngrok-free.app
   ```

4. Запустите бота: `python -m src.main`
5. В Telegram: `/start` — у администратора появится кнопка «Открыть дашборд»

## 3. Production (systemd)

Полная инструкция: [README.md — Запуск на удалённом сервере](../README.md#запуск-на-удалённом-сервере-ssh--systemd)

Кратко: деплой кода → `.env` → unit-файл → `systemctl enable --now cian-rental-bot`

## Чеклист первого запуска

| Проверка | Описание |
|----------|----------|
| BOT_TOKEN | Задан в .env |
| ADMIN_USER_ID | Ваш Telegram ID |
| venv активирован | `which python` указывает на .venv |
| Mini App (опционально) | ngrok запущен, WEBAPP_URL в .env |

---

Подробнее: [README.md](../README.md)
