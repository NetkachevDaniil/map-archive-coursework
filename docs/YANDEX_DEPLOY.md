# Перенос OrientMaps.Net с REG.RU на Yandex Cloud

Домен **o-maps.net.ru** остаётся на REG.RU. Меняется только сервер (A-запись) и настраивается почта через Yandex.

---

## Схема «было → стало»

```
БЫЛО:
  o-maps.net.ru → REG.RU DNS → 194.226.97.13 (VPS REG.RU) → Docker
  S3: Yandex Object Storage
  Почта: SMTP заблокирован на REG.RU VPS

СТАЛО:
  o-maps.net.ru → REG.RU DNS → IP Yandex Cloud → Docker
  S3: тот же бакет
  Почта: smtp.yandex.ru (noreply@o-maps.net.ru)
```

---

## Часть 1. Остановить сайт на REG.RU

```bash
ssh root@194.226.97.13
cd /opt/orientmaps
docker compose down
```

### Бэкап базы

```bash
docker compose up -d db
sleep 5
docker compose exec db pg_dump -U postgres orientmaps > /root/orientmaps_backup.sql
docker compose down
```

На ПК:

```powershell
scp root@194.226.97.13:/root/orientmaps_backup.sql D:\orientmaps_backup.sql
scp root@194.226.97.13:/opt/orientmaps/.env D:\orientmaps_env_backup.txt
```

Старый VPS отключай в панели REG.RU **только после** успешного переноса.

---

## Часть 2. Yandex Cloud — виртуальная машина

1. https://console.cloud.yandex.ru/ — облако, каталог, платёжный аккаунт.
2. **Compute Cloud → Виртуальные машины → Создать**:
   - Ubuntu 22.04, 2 vCPU, 2 GB RAM, 20 GB SSD
   - Публичный IP — автоматически (лучше статический)
   - SSH-ключ при создании
3. **Группа безопасности**: порты **22, 80, 443** (входящие TCP).

Запиши IP — например `158.160.xx.xx`.

```bash
ssh ubuntu@158.160.xx.xx
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ca-certificates gnupg nginx certbot python3-certbot-nginx
```

### Docker

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER
```

Переподключись по SSH.

---

## Часть 3. Приложение

```bash
sudo mkdir -p /opt/orientmaps && sudo chown $USER:$USER /opt/orientmaps
cd /opt/orientmaps
git clone https://github.com/NetkachevDaniil/map-archive-coursework.git .
cp .env.example .env
nano .env
```

Минимум в `.env`:

```env
SECRET_KEY=длинная-случайная-строка
DATABASE_URL=postgresql+psycopg2://postgres:СИЛЬНЫЙ_ПАРОЛЬ@db:5432/orientmaps
COOKIE_SECURE=true
FIRST_ADMIN_LOGIN=admin
FIRST_ADMIN_PASSWORD=...
OMAPS_SPB_LOGIN=o-maps.spb.ru
OMAPS_SPB_PASSWORD=...
OMAPS_MOSCOW_LOGIN=o-maps.moscow.ru
OMAPS_MOSCOW_PASSWORD=...
USE_S3=true
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_BUCKET_NAME=orientmaps-archive
S3_PUBLIC_BASE_URL=https://storage.yandexcloud.net/orientmaps-archive
SMTP_HOST=smtp.yandex.ru
SMTP_PORT=465
SMTP_USER=noreply@o-maps.net.ru
SMTP_PASSWORD=пароль_приложения
SMTP_SENDER=noreply@o-maps.net.ru
SMTP_USE_SSL=true
SMTP_USE_TLS=false
```

```bash
docker compose up -d --build
docker compose ps
```

Восстановление БД:

```powershell
scp D:\orientmaps_backup.sql ubuntu@158.160.xx.xx:/tmp/
```

```bash
docker compose exec -T db psql -U postgres orientmaps < /tmp/orientmaps_backup.sql
```

---

## Часть 4. Nginx

```bash
sudo nano /etc/nginx/sites-available/o-maps.net.ru
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
        # Импорт карт (скачивание 5 изображений) может занимать несколько минут
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        send_timeout 300s;
    }
}
```

```bash
sudo ln -sf /etc/nginx/sites-available/o-maps.net.ru /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

---

## Часть 5. DNS REG.RU

Панель REG.RU → домен **o-maps.net.ru** → DNS-записи:

| Тип | Имя | Значение |
|-----|-----|----------|
| A | @ | IP Yandex ВМ |
| A | www | IP Yandex ВМ |

Убери старый IP `194.226.97.13`. Подожди 5–30 мин.

```powershell
nslookup o-maps.net.ru
```

---

## Часть 6. HTTPS

```bash
sudo certbot --nginx -d o-maps.net.ru -d www.o-maps.net.ru
```

---

## Часть 7. Почта Yandex

1. https://admin.yandex.ru/ → добавить домен `o-maps.net.ru`.
2. Прописать MX и TXT в REG.RU (как покажет Yandex).
3. Создать ящик `noreply@o-maps.net.ru`.
4. Пароль приложения → в `SMTP_PASSWORD` в `.env`.
5. `docker compose up -d`

Проверка:

```bash
docker compose exec web python -c "import smtplib; s=smtplib.SMTP_SSL('smtp.yandex.ru',465,timeout=10); s.login('noreply@o-maps.net.ru','ПАРОЛЬ'); print('OK'); s.quit()"
```

---

## Часть 8. Git (обновление кода)

На ПК:

```powershell
cd D:\map-archive-coursework
git add -A
git commit -m "Восстановлено подтверждение email, инструкция деплоя на Yandex Cloud."
git push origin main
```

На сервере:

```bash
cd /opt/orientmaps
git pull origin main
docker compose up -d --build
```

---

## Ссылки

| | URL |
|--|-----|
| Yandex Cloud | https://console.cloud.yandex.ru/ |
| REG.RU | https://www.reg.ru/user/account/ |
| GitHub | https://github.com/NetkachevDaniil/map-archive-coursework |
| Сайт | https://o-maps.net.ru |
