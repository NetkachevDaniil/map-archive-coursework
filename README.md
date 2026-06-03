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

- Регистрация/вход пользователей (JWT), подтверждение email
- Две роли: `user` и `admin`
- Уникальный админ создаётся автоматически при первом старте
- Лента новостей с картами
- Каталог-архив в формате таблицы с вкладками:
  - Карты
  - Соревнования
  - Спортсмены
- Профиль пользователя с сеткой карт (как в соцсетях)
- Страница карты (детали, лайки, комментарии, скачивание)
- Страница добавления карты (только для обычного пользователя)
- Очередь модерации парсинга (только для админа):
  - импорт изображений из поддерживаемых источников
  - редактирование метаданных
  - публикация/отклонение/удаление
- Docker + docker-compose

## Источники парсинга (в текущей версии)

Рабочие веб-адаптеры:

- `https://maps.o-stuff.net/ru/lastmaps`
- `https://o-mephi.net/index.php?pid=145`

Важно: VK/Telegram/Яндекс.Картинки обычно требуют отдельные API/авторизацию/устойчивые селекторы. Для них в проекте заложена архитектура расширяемых адаптеров, но нужны отдельные ключи и согласованная реализация под конкретные правила доступа.

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
- `FIRST_ADMIN_EMAIL`
- `FIRST_ADMIN_PASSWORD`

Если админ уже есть в БД, второй не создаётся.

## Подтверждение email

- Если SMTP не настроен, ссылка подтверждения выводится в консоль сервера (`[EMAIL DEBUG] ...`).
- Для боевого режима заполните SMTP-параметры в `.env`.

## Настройка почты через Mail.ru

1. Войдите в нужный ящик Mail.ru.
2. Включите двухфакторную аутентификацию.
3. Создайте пароль для внешнего приложения (SMTP) в настройках безопасности Mail.ru.
4. В `.env` задайте:

```env
SMTP_HOST=smtp.mail.ru
SMTP_PORT=465
SMTP_USER=your_mailbox@mail.ru
SMTP_PASSWORD=пароль_приложения_mailru
SMTP_SENDER=your_mailbox@mail.ru
SMTP_USE_SSL=true
SMTP_USE_TLS=false
SMTP_TIMEOUT_SECONDS=20
```

5. Перезапустите сервер приложения.
6. Проверьте регистрацию нового пользователя — письмо подтверждения должно прийти в почту.

Альтернатива для порта `587`:

```env
SMTP_PORT=587
SMTP_USE_SSL=false
SMTP_USE_TLS=true
```

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

- Добавить API-интеграции для VK/Telegram (официальные токены и правила платформ)
- Добавить presigned URL для приватного S3
- Расширить фильтрацию каталога по датам/масштабу/автору отдельными полями формы
- Добавить тесты на роуты и сервис парсинга
