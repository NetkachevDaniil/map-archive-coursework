# OrientMaps.Net

Курсовой проект — веб-архив карт спортивного ориентирования.

Сайт: [o-maps.net.ru](https://o-maps.net.ru/)  
Репозиторий: [github.com/NetkachevDaniil/map-archive-coursework](https://github.com/NetkachevDaniil/map-archive-coursework)

**Стек:** Python, FastAPI, Jinja2, PostgreSQL, SQLAlchemy, Alembic, JWT (cookie), Yandex Object Storage, Docker.

## Что умеет

Пользователь регистрируется, подтверждает email и может добавлять карты, ставить лайки, оставлять комментарии. Есть лента, каталог (карты и спортсмены), профили. Администратор импортирует карты с [o-maps.spb.ru](https://o-maps.spb.ru/), проверяет их в очереди модерации и публикует.

Импорт: отдельно Санкт-Петербург и Москва, только карты с 2020 года, до 5 штук за один запуск. Изображения хранятся в S3 (JPEG/PNG, WebP и GIF конвертируются в JPEG).

## Запуск локально

```bash
cp .env.example .env   # заполнить DATABASE_URL, SECRET_KEY, SMTP, S3
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Открыть http://localhost:8000. Админ создаётся при первом старте из `FIRST_ADMIN_*` в `.env`.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

Порт PostgreSQL наружу не открывается. Для отладки с хоста:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## Деплой

Инструкция: [docs/YANDEX_DEPLOY.md](docs/YANDEX_DEPLOY.md).

На сервере: `COOKIE_SECURE=true`, сильные пароли, в nginx — `client_max_body_size 55M` и `proxy_read_timeout 300s` (импорт карт может занимать несколько минут).

## Структура проекта

```
app/
  routers/     — маршруты (auth, posts, catalog, admin, files)
  services/    — парсер, почта, S3, bootstrap
  models/      — SQLAlchemy-модели
  templates/   — Jinja2-шаблоны
alembic/       — миграции БД
tests/         — pytest
```

Парсер: `app/services/parser_service.py`, кнопки импорта — `/admin/parsing`.
