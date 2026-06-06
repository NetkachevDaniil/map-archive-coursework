# Как подключить домен o-maps.net.ru — пошагово

Домен **куплен** — это только «адрес» в интернете. Чтобы по нему открывался ваш сайт OrientMaps.Net, нужно связать домен с **сервером**, где запущено приложение.

---

## Что понадобится

1. **Домен** `o-maps.net.ru` (у вас уже есть).
2. **VPS/сервер** — виртуальная машина с белым IP (например Timeweb, Selectel, REG.RU VPS, Yandex Cloud).
3. **Сайт на сервере** — OrientMaps запущен через Docker или `uvicorn`.
4. Доступ к **панели регистратора домена** (где покупали `.net.ru`).

---

## Шаг 1. Узнать IP сервера

На VPS выполните:

```bash
curl -4 ifconfig.me
```

Или посмотрите IP в панели хостинга. Пример: `185.12.34.56`.

Этот IP нужно «привязать» к домену.

---

## Шаг 2. Настроить DNS у регистратора

Зайдите в личный кабинет, где куплен домен → раздел **DNS / Управление зоной / DNS-серверы**.

### Если DNS ведёт регистратор

Добавьте записи:

| Тип | Имя (Host) | Значение | TTL |
|-----|------------|----------|-----|
| **A** | `@` | `185.12.34.56` (ваш IP) | 3600 |
| **A** | `www` | `185.12.34.56` (тот же IP) | 3600 |

- `@` — это сам домен `o-maps.net.ru`
- `www` — это `www.o-maps.net.ru`

Сохраните. Обновление DNS занимает от **5 минут до 24 часов**.

### Проверка с вашего ПК

```powershell
nslookup o-maps.net.ru
```

В ответе должен быть ваш IP сервера.

---

## Шаг 3. Запустить сайт на сервере

### Вариант A — Docker (рекомендуется)

На сервере в папке проекта:

```bash
git clone https://github.com/NetkachevDaniil/map-archive-coursework.git
cd map-archive-coursework
cp .env.example .env
# отредактируйте .env: DATABASE_URL, S3, SECRET_KEY и т.д.
docker compose up -d --build
```

Приложение обычно слушает порт **8000** внутри контейнера.

### Вариант B — вручную

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

## Шаг 4. Nginx — «входная дверь» для домена

Nginx принимает запросы на `o-maps.net.ru` и передаёт их вашему FastAPI.

Установка (Ubuntu):

```bash
sudo apt update
sudo apt install nginx
```

Файл `/etc/nginx/sites-available/o-maps`:

```nginx
server {
    listen 80;
    server_name o-maps.net.ru www.o-maps.net.ru;

    client_max_body_size 25M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Активация:

```bash
sudo ln -s /etc/nginx/sites-available/o-maps /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Откройте в браузере: `http://o-maps.net.ru` — должен открыться сайт (пока без HTTPS).

---

## Шаг 5. HTTPS (замок в браузере)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d o-maps.net.ru -d www.o-maps.net.ru
```

Certbot сам выпустит бесплатный сертификат Let's Encrypt и настроит редирект HTTP → HTTPS.

После этого сайт: **https://o-maps.net.ru**

---

## Шаг 6. Что где лежит — краткая схема

```
Пользователь в браузере
        ↓
   DNS: o-maps.net.ru → IP сервера
        ↓
   Nginx (порт 443 HTTPS)
        ↓
   FastAPI / uvicorn (порт 8000)
        ↓
   PostgreSQL + S3 (картинки)
```

---

## Частые проблемы

| Проблема | Причина | Решение |
|----------|---------|---------|
| «Сайт не открывается» | DNS ещё не обновился | Подождать, проверить `nslookup` |
| «502 Bad Gateway» | приложение не запущено | `docker compose ps`, перезапуск |
| «Connection refused» | Nginx не настроен / firewall | открыть порты 80 и 443 |
| Картинки не грузятся | S3 ключи в `.env` | проверить `USE_S3`, `S3_*` |

---

## Favicon (иконка во вкладке)

Уже в проекте: `app/static/favicon.svg`, подключён в `base.html`.

После деплоя обновите страницу с Ctrl+F5 — во вкладке будет иконка **OM**.

---

## Если сайт только на вашем компьютере (без VPS)

Домен **не сможет** указывать на `localhost`. Нужен либо VPS, либо туннель (ngrok и т.п.) — для курсового и production обычно берут VPS.

---

## Итог — минимальный чеклист

- [ ] Есть VPS с белым IP
- [ ] A-запись `@` и `www` → IP VPS
- [ ] `nslookup o-maps.net.ru` показывает правильный IP
- [ ] Приложение запущено на порту 8000
- [ ] Nginx проксирует домен на 8000
- [ ] Certbot выдал HTTPS
- [ ] Открывается https://o-maps.net.ru
