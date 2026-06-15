# Подключение домена o-maps.net.ru (REG.RU) — полная инструкция

Домен **куплен на REG.RU** — это адрес сайта в интернете. Чтобы по адресу `https://o-maps.net.ru` открывался **OrientMaps.Net**, нужно связать домен с сервером, где запущено приложение.

---

## Что у вас уже должно быть

| Компонент | Зачем |
|-----------|--------|
| Домен `o-maps.net.ru` на REG.RU | Адрес сайта |
| VPS (сервер с белым IP) | Где работает FastAPI + PostgreSQL |
| Yandex Object Storage (S3) | Хранение изображений карт |
| Git-репозиторий проекта | Код приложения |

> Домен **не может** указывать на ваш домашний ПК (`localhost`). Нужен VPS с публичным IP.

---

## Часть 1. REG.RU — настройка DNS

### Шаг 1.1. Войти в личный кабинет

1. Откройте [https://www.reg.ru](https://www.reg.ru) → **Войти**.
2. **Домены** → выберите **o-maps.net.ru**.
3. Откройте раздел **«DNS-серверы и управление зоной»** (или **«Управление DNS»**).

### Шаг 1.2. DNS-серверы

**Вариант А (проще):** оставить DNS REG.RU (ns1.reg.ru, ns2.reg.ru) — тогда записи добавляете прямо в панели REG.RU.

**Вариант Б:** если VPS-провайдер даёт свои NS — укажите их в REG.RU и настраивайте DNS у хостера.

Для курсового проекта обычно достаточно **варианта А**.

### Шаг 1.3. Узнать IP вашего VPS

На сервере (SSH):

```bash
curl -4 ifconfig.me
```

Или IP указан в панели Timeweb / Selectel / REG.RU VPS. Пример: `185.12.34.56`.

### Шаг 1.4. Добавить DNS-записи в REG.RU

В зоне домена **o-maps.net.ru** добавьте:

| Тип | Subdomain / Host | Значение | TTL |
|-----|------------------|----------|-----|
| **A** | `@` | `185.12.34.56` (ваш IP VPS) | 3600 |
| **A** | `www` | `185.12.34.56` (тот же IP) | 3600 |

- `@` — это сам домен `o-maps.net.ru`
- `www` — это `www.o-maps.net.ru`

Сохраните. Обновление DNS: **от 5 минут до 24 часов**.

### Шаг 1.5. Проверка с вашего ПК (Windows)

```powershell
nslookup o-maps.net.ru
```

В ответе должен быть **IP вашего VPS**. Если старый IP или «не найден» — подождите или проверьте записи в REG.RU.

---

## Часть 2. VPS — подготовка сервера

Подключитесь по SSH (логин/пароль или ключ из панели REG.RU / хостера):

```bash
ssh root@185.12.34.56
```

### Шаг 2.1. Обновление и базовые пакеты (Ubuntu 22.04/24.04)

```bash
apt update && apt upgrade -y
apt install -y git docker.io docker-compose-plugin nginx certbot python3-certbot-nginx ufw
```

### Шаг 2.2. Firewall

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
```

---

## Часть 3. Развёртывание OrientMaps.Net

### Шаг 3.1. Клонировать проект

```bash
cd /opt
git clone https://github.com/NetkachevDaniil/map-archive-coursework.git orientmaps
cd orientmaps
```

### Шаг 3.2. Файл `.env`

```bash
cp .env.example .env
nano .env
```

Минимально заполните:

```env
SECRET_KEY=длинная-случайная-строка-32+символов
DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/orientmaps

USE_S3=true
S3_ENDPOINT_URL=https://storage.yandexcloud.net
S3_ACCESS_KEY_ID=ваш_ключ
S3_SECRET_ACCESS_KEY=ваш_секрет
S3_BUCKET_NAME=orientmaps-archive
S3_REGION=ru-central1

FIRST_ADMIN_LOGIN=admin
FIRST_ADMIN_EMAIL=car_specific@mail.ru
FIRST_ADMIN_PASSWORD=надёжный_пароль
```

### Шаг 3.3. Запуск Docker

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f app
```

Приложение слушает **порт 8000** внутри сервера.

---

## Часть 4. Nginx — привязка домена к приложению

Создайте конфиг:

```bash
nano /etc/nginx/sites-available/o-maps.net.ru
```

```nginx
server {
    listen 80;
    server_name o-maps.net.ru www.o-maps.net.ru;

    client_max_body_size 55M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        send_timeout 300s;
    }
}
```

Активация:

```bash
ln -s /etc/nginx/sites-available/o-maps.net.ru /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

Проверка: откройте `http://o-maps.net.ru` — должен открыться сайт (пока без HTTPS).

---

## Часть 5. HTTPS (Let's Encrypt)

```bash
certbot --nginx -d o-maps.net.ru -d www.o-maps.net.ru
```

- Укажите email для уведомлений.
- Согласитесь с условиями.
- Certbot сам настроит редирект HTTP → HTTPS.

Итог: **https://o-maps.net.ru**

Сертификат продлевается автоматически (cron certbot).

---

## Часть 6. REG.RU — что ещё проверить в панели

1. **Домен активен** — оплачен, не просрочен.
2. **DNS-записи** — A для `@` и `www` указывают на IP VPS.
3. **Регистрация** — вход и регистрация по логину и паролю, без подтверждения email. На VPS REG.RU исходящие SMTP-порты (465/587) заблокированы, поэтому отправка писем из приложения не используется.

---

## Схема работы

```
Браузер → o-maps.net.ru (DNS REG.RU → IP VPS)
       → Nginx :443 HTTPS
       → FastAPI :8000
       → PostgreSQL + Yandex S3 (картинки)
```

---

## Частые проблемы

| Симптом | Решение |
|---------|---------|
| «Сайт не открывается» | Проверить `nslookup`, подождать DNS |
| «502 Bad Gateway» | `docker compose ps`, перезапуск `docker compose up -d` |
| «Connection refused» | Nginx не запущен или firewall блокирует 80/443 |
| Картинки не грузятся | Проверить `USE_S3` и ключи в `.env` |
| REG.RU показывает «парковку» | A-запись не на VPS или DNS ещё не обновился |

---

## Чеклист перед сдачей курсовой

- [ ] A-запись `@` и `www` → IP VPS в REG.RU
- [ ] `nslookup o-maps.net.ru` → правильный IP
- [ ] `docker compose up -d` на сервере
- [ ] Nginx проксирует на порт 8000
- [ ] Certbot выдал HTTPS
- [ ] Открывается https://o-maps.net.ru
- [ ] Регистрация / вход / каталог / модерация работают
- [ ] Картинки грузятся из S3

---

## Обновление сайта после изменений в коде

На VPS:

```bash
cd /opt/orientmaps
git pull
docker compose up -d --build
```
