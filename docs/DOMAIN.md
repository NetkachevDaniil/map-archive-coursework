# Подключение домена o-maps.net.ru

Краткая инструкция для публикации OrientMaps на вашем домене.

## 1. DNS у регистратора домена

В панели управления доменом `o-maps.net.ru` добавьте записи:

| Тип | Имя | Значение | TTL |
|-----|-----|----------|-----|
| A | `@` | IP вашего сервера (VPS) | 300–3600 |
| A | `www` | тот же IP | 300–3600 |

Если сайт будет на другом хостинге — уточните у провайдера, нужна ли CNAME вместо A.

Проверка (через несколько минут):

```powershell
nslookup o-maps.net.ru
```

## 2. Сервер: Nginx + приложение

Пример для VPS с Ubuntu и приложением на порту `8000`:

```nginx
server {
    listen 80;
    server_name o-maps.net.ru www.o-maps.net.ru;

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Запуск приложения (из каталога проекта):

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Для production лучше использовать systemd или Docker из `docker-compose.yml`.

## 3. HTTPS (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d o-maps.net.ru -d www.o-maps.net.ru
```

Certbot сам настроит редирект HTTP → HTTPS.

## 4. Переменные окружения

В `.env` на сервере проверьте:

- `SECRET_KEY` — уникальный ключ
- `DATABASE_URL` — PostgreSQL
- `USE_S3`, `S3_*` — хранилище файлов
- при необходимости `SITE_BACKGROUND_URL`, `DEFAULT_AVATAR_URL`

## 5. Favicon (иконка во вкладке браузера)

В проекте уже добавлен файл `app/static/favicon.svg` (минималистичные буквы **O** и **M** в чёрно-оранжевой теме).

Подключение в шаблоне:

```html
<link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
```

При желании можно дополнительно положить `favicon.ico` в `app/static/` и добавить:

```html
<link rel="icon" href="/static/favicon.ico" sizes="any">
```

## 6. Редирект www → без www (опционально)

В Nginx после получения SSL:

```nginx
server {
    listen 443 ssl;
    server_name www.o-maps.net.ru;
    return 301 https://o-maps.net.ru$request_uri;
}
```

## 7. Проверка после деплоя

1. Открыть `https://o-maps.net.ru`
2. Убедиться, что картинки грузятся из S3
3. Проверить вход, каталог, модерацию
4. Во вкладке браузера должна отображаться иконка OM

Если DNS только что изменили, полное обновление может занять до 24 часов.
