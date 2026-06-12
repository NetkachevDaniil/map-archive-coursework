# OrientMaps Coursework

Веб-приложение архива карт спортивного ориентирования на стеке:

- Python + FastAPI
- Jinja2
- PostgreSQL
- SQLAlchemy
- Alembic
- JWT (через cookie)
- S3 (Yandex Object Storage) или локальное хранилище

## Что реализовано

- Регистрация и вход по логину и паролю (JWT в cookie)
- Две роли: `user` и `admin`
- Уникальный админ создаётся автоматически при первом старте
- Лента новостей с картами
- Каталог-архив в формате таблицы с вкладками:
  - Карты (поиск, фильтр по региону, сортировка)
  - Спортсмены (поиск пользователей)
- Профиль пользователя с сеткой карт (как в соцсетях)
- Страница карты (детали, лайки, комментарии, скачивание)
- Страница добавления карты (только для авторизованного пользователя)
- Очередь модерации парсинга (только для админа):
  - импорт изображений из поддерживаемых источников
  - редактирование метаданных
  - публикация или удаление
- Docker + docker-compose

Подтверждение email и отправка писем **не используются**: на VPS-хостинге REG.RU исходящие SMTP-порты недоступны. В перспективе планируется двухфакторная аутентификация.

## Источники парсинга (в текущей версии)

- `https://o-maps.spb.ru/` — листы **Санкт-Петербург** и **Москва** (JS-фиды из репозитория efradkin/o-maps)

Изображения сохраняются в S3 или локально и отдаются через `/files/...` на сервере приложения.

## Быстрый запуск (локально, без Docker)

1. Создайте БД PostgreSQL:
   - База: `orientmaps`
   - Пользователь: `postgres`
   - Пароль: `postgres` (или свой, тогда поправьте `.env`)
2. Скопируйте `.env.example` в `.env`
3. Создайте виртуальное окружение и установите зависимости:
   - `python -m venv .venv`
   - `.venv\Scripts\activate`
   - `pip install -r requirements.txt`
4. Выполните миграции:
   - `alembic upgrade head`
5. Запустите приложение:
   - `uvicorn app.main:app --reload`
6. Откройте:
   - [http://localhost:8000](http://localhost:8000)

## Учетка админа по умолчанию

Берётся из `.env`:

- `FIRST_ADMIN_LOGIN`
- `FIRST_ADMIN_EMAIL` — служебный email записи администратора в БД
- `FIRST_ADMIN_PASSWORD`

Если админ уже есть в БД, второй не создаётся.

## Подключение Yandex Cloud S3

1. В Yandex Cloud создайте бакет в Object Storage.
2. Создайте сервисный аккаунт и статический ключ доступа (Access key + Secret key).
3. Убедитесь, что у ключа есть права на бакет (`storage.editor` минимум).
4. В `.env` установите:

```env
USE_S3=true
S3_ENDPOINT_URL=https://storage.yandexcloud.net
S3_ACCESS_KEY_ID=ваш_access_key
S3_SECRET_ACCESS_KEY=ваш_secret_key
S3_BUCKET_NAME=имя_бакета
S3_REGION=ru-central1
S3_PUBLIC_BASE_URL=https://storage.yandexcloud.net/имя_бакета
```

5. Перезапустите приложение.

Если бакет закрытый, для скачивания/просмотра лучше добавить presigned URLs (следующий шаг развития).

## Docker

1. Скопируйте `.env.example` в `.env`
2. Убедитесь, что `DATABASE_URL` внутри контейнера указывает на сервис `db`:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/orientmaps
```

3. Запуск:
   - `docker compose up --build`
4. Приложение:
   - [http://localhost:8000](http://localhost:8000)

## Работа в PyCharm

1. `File -> Open` и выберите папку проекта `D:\map-archive-coursework`.
2. Настройте интерпретатор:
   - `Settings -> Project -> Python Interpreter`
   - Создать `.venv` в проекте.
3. Установите зависимости (`requirements.txt`).
4. Создайте `.env` из `.env.example`.
5. Создайте Run Configuration:
   - Тип: `Python`
   - Module name: `uvicorn`
   - Parameters: `app.main:app --reload`
   - Working directory: корень проекта.
6. Запустите конфигурацию.
7. Для миграций откройте терминал PyCharm:
   - `alembic upgrade head`

## Что дальше по проекту

- Двухфакторная аутентификация (при появлении канала доставки кодов)
- Добавить API-интеграции для VK/Telegram (официальные токены и правила платформ)
- Добавить presigned URL для приватного S3
- Расширить фильтрацию каталога по датам/масштабу/автору отдельными полями формы
- Добавить тесты на роуты и сервис парсинга
