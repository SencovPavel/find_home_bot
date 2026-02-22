# Rental Bot

Telegram-бот для мониторинга объявлений аренды квартир на ЦИАН, Авито и Яндекс Недвижимости. Автоматически проверяет новые объявления по заданным фильтрам и отправляет подходящие варианты в чат.

## Возможности

- Мониторинг трёх площадок: ЦИАН, Авито, Яндекс Недвижимость
- Пошаговая настройка фильтров через inline-клавиатуры (8 шагов)
- Фильтрация по городу, количеству комнат, цене, площади, кухне, типу ремонта
- Фильтр «без комиссии»
- Эвристическое определение запрета на животных в описании
- Отображение ближайшего метро и расстояния до него
- Отображение источника объявления (ЦИАН / Авито / Яндекс)
- Периодическая проверка новых объявлений (по умолчанию каждые 5 минут)
- Отправка фото объявления вместе с описанием
- Уведомление при отсутствии объявлений по фильтрам («по таким требованиям вы можете не найти объект»)
- Кнопки навигации: Reply-клавиатура и inline-кнопки для быстрого доступа к командам
- Mini App дашборд (статус мониторинга, сводка фильтров) — только для администратора

## Требования

- Python 3.9+
- Telegram Bot Token (от [@BotFather](https://t.me/BotFather))

## Установка

```bash
# Клонировать и перейти в директорию
cd bot

# Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Установить зависимости
pip install -e .
```

## Настройка

Скопируйте `.env.example` в `.env` и заполните:

```bash
cp .env.example .env
```

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота от @BotFather |
| `ADMIN_USER_ID` | Ваш Telegram user ID (узнать: [@userinfobot](https://t.me/userinfobot)) |
| `CHECK_INTERVAL_MINUTES` | Интервал проверки в минутах (по умолчанию 5) |
| `GROUP_CHAT_ID` | ID группы для отправки объявлений администратору (опционально) |
| `GROUP_TOPIC_ID` | ID темы в группе (опционально, вместе с GROUP_CHAT_ID) |
| `WEBAPP_URL` | HTTPS-URL Mini App (опционально, для дашборда) |
| `WEBAPP_HOST` | Хост для web-сервера (по умолчанию 0.0.0.0) |
| `WEBAPP_PORT` | Порт для web-сервера (по умолчанию 8080) |

## Telegram Mini App (дашборд)

Дашборд со статусом мониторинга и сводкой фильтров — доступен **только администратору** (ADMIN_USER_ID).

Если задан `WEBAPP_URL`, при запуске поднимается web-сервер; в `/start` у администратора появляется кнопка «Открыть дашборд». Mini App требует HTTPS.

**Локальная разработка:** используйте ngrok: `ngrok http 8080` → скопируйте HTTPS-URL в `WEBAPP_URL`.

## Запуск

```bash
python -m src.main
```

## Автотесты

```bash
# Установить dev-зависимости
python -m pip install ".[dev]"

# Запустить тесты (требуется .env с BOT_TOKEN и ADMIN_USER_ID)
pytest

# Запустить тесты с подробным coverage-отчётом
pytest --cov=src --cov-report=term-missing
```

В проекте включен порог покрытия в `pyproject.toml` через `pytest-cov`. В CI переменные `BOT_TOKEN` и `ADMIN_USER_ID` задаются автоматически.

## Отправка в тему группы

Для администратора объявления можно отправлять в тему группы вместо личных сообщений. Два способа настройки:

1. **Команда /settopic** — добавьте бота в группу с включёнными темами, отправьте `/settopic` **внутри нужной темы**. Бот сохранит chat_id и message_thread_id в БД.
2. **Переменные окружения** — задайте `GROUP_CHAT_ID` и `GROUP_TOPIC_ID` в `.env`. Приоритет у значений из БД (если заданы через /settopic).

Обычные пользователи продолжают получать объявления в личку.

## Команды бота

| Команда | Описание |
|---|---|
| `/start` | Приветствие и инструкция |
| `/search` | Настроить фильтры поиска |
| `/filters` | Показать текущие фильтры |
| `/pause` | Приостановить мониторинг |
| `/resume` | Возобновить мониторинг |
| `/settopic` | Настроить тему группы для объявлений (только администратор, вызывать внутри темы) |

## Структура проекта

```
src/
  main.py              — точка входа
  config.py            — конфигурация из .env
  bot/
    handlers.py        — обработчики команд
    keyboards.py       — inline-клавиатуры
    formatter.py       — форматирование сообщений
  webapp/
    routes.py          — API дашборда
    validation.py      — валидация initData
    static/
      index.html       — страница дашборда
  parser/
    base.py            — общий интерфейс и утилиты парсеров
    cian.py            — парсер ЦИАН
    avito.py           — парсер Авито
    yandex_realty.py   — парсер Яндекс Недвижимости
    models.py          — модели данных (Listing, UserFilter, Source)
  storage/
    database.py        — SQLite (фильтры, просмотренные объявления)
  scheduler/
    monitor.py         — периодическая проверка всех площадок
```

## Запуск на удалённом сервере (SSH + systemd)

Ниже production-сценарий для Ubuntu/Debian без Docker.

### 1) Подготовка сервера

```bash
ssh root@YOUR_SERVER_IP
apt update && apt install -y python3 python3-venv python3-pip git
adduser --disabled-password --gecos "" botuser
usermod -aG sudo botuser
```

### 2) Деплой кода под сервисным пользователем

```bash
ssh botuser@YOUR_SERVER_IP
mkdir -p /home/botuser/apps
cd /home/botuser/apps
git clone <YOUR_REPOSITORY_URL> bot
cd bot
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install .
```

### 3) Настройка окружения

```bash
cd /home/botuser/apps/bot
cp .env.example .env
nano .env
chmod 600 .env
```

Обязательные поля:
- `BOT_TOKEN`
- `ADMIN_USER_ID`
- `CHECK_INTERVAL_MINUTES`

Опционально: `DB_PATH`, `WEBAPP_URL` (для Mini App дашборда, нужен HTTPS).

### 4) Создание systemd unit

```bash
sudo nano /etc/systemd/system/cian-rental-bot.service
```

Пример unit-файла:

```ini
[Unit]
Description=CIAN Rental Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=botuser
Group=botuser
WorkingDirectory=/home/botuser/apps/bot
EnvironmentFile=/home/botuser/apps/bot/.env
ExecStart=/home/botuser/apps/bot/.venv/bin/python -m src.main
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/home/botuser/apps/bot

[Install]
WantedBy=multi-user.target
```

### 5) Запуск и проверка

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cian-rental-bot
sudo systemctl status cian-rental-bot
sudo journalctl -u cian-rental-bot -f
```

### 6) Обновление версии

```bash
ssh botuser@YOUR_SERVER_IP
cd /home/botuser/apps/bot
git pull
.venv/bin/pip install .
sudo systemctl restart cian-rental-bot
sudo systemctl status cian-rental-bot
```

### 7) Rollback

```bash
ssh botuser@YOUR_SERVER_IP
cd /home/botuser/apps/bot
git log --oneline -n 5
git checkout <PREVIOUS_COMMIT_HASH>
.venv/bin/pip install .
sudo systemctl restart cian-rental-bot
```

## CI/CD (GitHub Actions -> SSH -> systemd)

Автоматический деплой выполняется при `push` в `main`, но только если job с тестами прошел успешно.

### Что происходит в pipeline

1. `test`:
   - устанавливается Python;
   - устанавливаются dev-зависимости;
   - запускается `pytest` с переменными `BOT_TOKEN` и `ADMIN_USER_ID` (включая порог coverage из `pyproject.toml`).
2. `deploy` (только после `test`):
   - подключение к серверу по SSH-ключу;
   - `git pull`, `pip install .`, перезапуск systemd-сервиса.

Workflow: `.github/workflows/ci-cd.yml`

### 1) Создайте secrets в GitHub

В репозитории: `Settings -> Secrets and variables -> Actions -> New repository secret`.

Обязательные secrets:

| Secret | Назначение |
|---|---|
| `DEPLOY_KEY` | Приватный SSH-ключ для деплоя (целиком, включая BEGIN/END) |
| `SSH_KNOWN_HOSTS` | Содержимое `~/.ssh/known_hosts` для хоста (или оставить пустым — используется ssh-keyscan) |
| `SSH_HOST` | Адрес сервера (IP или домен) |
| `SSH_USER` | Пользователь для SSH (например `botuser`) |

Путь к приложению и имя systemd-сервиса заданы в workflow; при необходимости отредактируйте `.github/workflows/ci-cd.yml` (шаг «Deploy via SSH»).

### 2) Подготовьте SSH-ключ для деплоя

Локально:

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ./bot_deploy_key
```

- содержимое `bot_deploy_key` сохраните в `DEPLOY_KEY`;
- содержимое `bot_deploy_key.pub` добавьте в `~/.ssh/authorized_keys` на сервере.

### 3) Разрешите restart сервиса без пароля (sudoers)

На сервере:

```bash
sudo visudo -f /etc/sudoers.d/bot-deploy
```

Добавьте строку:

```text
botuser ALL=NOPASSWD: /bin/systemctl restart cian-rental-bot, /bin/systemctl status cian-rental-bot, /bin/systemctl is-active cian-rental-bot
```

Проверьте:

```bash
sudo -l -U botuser
```

### 4) Первичная проверка после включения CI/CD

1. Сделайте небольшой commit в `main`.
2. Откройте `Actions` и дождитесь завершения `CI/CD`.
3. На сервере проверьте статус systemd-сервиса (имя указано в workflow, например `find-home-bot`).

Если `test` падает, деплой не запускается — это ожидаемое поведение.
