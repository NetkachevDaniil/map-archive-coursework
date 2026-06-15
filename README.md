# OrientMaps Coursework

Веб-приложение архива карт спортивного ориентирования **OrientMaps.Net** ([o-maps.net.ru](https://o-maps.net.ru/)).

Стек: Python, FastAPI, Jinja2, PostgreSQL, SQLAlchemy, Alembic, JWT (cookie), Yandex Object Storage.

## Функциональность

- Регистрация с подтверждением email (SMTP) и вход по логину/email
- Роли `user` и `admin`; админ создаётся при первом старте из `.env`
- Лента, каталог (карты и спортсмены), профили, добавление карт
- Лайки, комментарии, скачивание изображений
- Импорт карт из [o-maps.spb.ru](https://o-maps.spb.ru/) с модерацией (отдельно СПб и Москва)
- Ограничение частоты запросов (защита от «спама» кнопками)
- Лимит размера файлов карт: **50 МБ**

## Источник парсинга O-Maps

Сайт **o-maps.spb.ru** — единая точка входа. Страницы `sheet-spb.html` и `sheet-moscow.html` подгружают каталоги карт из JavaScript-файлов репозитория [efradkin/o-maps](https://github.com/efradkin/o-maps) на GitHub (`raw.githubusercontent.com`). Сами изображения лежат либо на `o-maps.spb.ru/original_maps/...`, либо в том же репозитории в каталоге `maps/...`.

При импорте:

- парсятся только карты **с 2020 года** (год обязателен в метаданных);
- за один запуск — до **5 новых** карт выбранного региона;
- карты СПб публикуются от профиля `o-maps.spb.ru`, Москвы — от `o-maps.moscow.ru`;
- предпочтение форматов JPEG/PNG; WebP конвертируется в JPEG без уменьшения разрешения.

## Безопасность

| Риск | Решение в проекте |
|------|-------------------|
| PostgreSQL доступен из интернета | В `docker-compose.yml` порт **5432 не пробрасывается** на хост. Для локальной отладки: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` |
| Слабый пароль БД | На продакшене задайте сильный `POSTGRES_PASSWORD` в `.env` и в `DATABASE_URL` |
| Секреты в Git | `.env` в `.gitignore`; в репозитории только `.env.example` |
| Прямой доступ к `uploads/` | Маршрут `/media` отключён по умолчанию (`EXPOSE_LOCAL_MEDIA=false`); файлы отдаются через `/files/` |
| Перебор форм / спам кнопками | Middleware rate limit: при превышении лимита IP временно блокируется |
| Cookie по HTTP | На HTTPS установите `COOKIE_SECURE=true` |

**Важно:** если раньше на VPS был открыт порт 5432 с паролем `postgres`, смените пароль БД и закройте порт в файрволе облака.

## Быстрый запуск (локально)

1. PostgreSQL: база `orientmaps`, пользователь `postgres`
2. `cp .env.example .env` и заполните переменные
3. `python -m venv .venv` → активация → `pip install -r requirements.txt`
4. `alembic upgrade head`
5. `uvicorn app.main:app --reload` → [http://localhost:8000](http://localhost:8000)

## Docker

```bash
cp .env.example .env
# DATABASE_URL=postgresql+psycopg2://postgres:ВАШ_ПАРОЛЬ@db:5432/orientmaps
docker compose up --build
```

Доступ к PostgreSQL с хоста (только для разработки):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

На продакшене (Yandex Cloud): `COOKIE_SECURE=true`, сильные пароли, порты **22, 80, 443** — без 5432.

## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `FIRST_ADMIN_*` | Учётная запись администратора |
| `OMAPS_SPB_*`, `OMAPS_MOSCOW_*` | Служебные профили для импортированных карт |
| `SMTP_*` | Подтверждение email |
| `S3_*`, `USE_S3` | Yandex Object Storage |
| `MAX_UPLOAD_BYTES` | Лимит размера карты (по умолчанию 50 МБ) |
| `PARSER_MIN_YEAR` | Минимальный год импорта (2020) |
| `RATE_LIMIT_*` | Параметры ограничения частоты запросов |

## Деплой

См. `docs/YANDEX_DEPLOY.md` и `docs/DOMAIN.md`.

## Разработка в PyCharm

Run configuration: module `uvicorn`, parameters `app.main:app --reload`, working directory — корень проекта.
