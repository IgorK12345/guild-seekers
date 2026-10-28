# Размещение на VPS

Ubuntu 24.04, Docker Engine и Compose plugin. Проект: `/opt/guild-seekers`.
Создайте закрытый `.env` (права 600):

```dotenv
POSTGRES_PASSWORD=GENERATE_RANDOM_HEX
SECRET_KEY=GENERATE_RANDOM_SECRET
DOMAIN=guild-seekers.online
PUBLIC_ORIGIN=https://guild-seekers.online
SECURE_COOKIE=true
```

`POSTGRES_PASSWORD` должен быть безопасен для URL, например случайные hex-символы.
Домен должен иметь A-запись на IP сервера; 80/443 должны быть доступны извне.

```sh
docker compose -f compose.yaml -f compose.production.yaml up -d --build
docker compose -f compose.yaml -f compose.production.yaml ps
```

Caddy получает и продлевает сертификат, перенаправляет HTTP на HTTPS. PostgreSQL
не публикует порт наружу, приложение доступно на хосте только через loopback.
Не открывайте порт 8000 для всех: доверие proxy-заголовкам рассчитано на Caddy.
База и сертификаты хранятся в постоянных Docker volumes. Не выполняйте `down -v`.

На сервере создаётся новая база: локальные аккаунты и прогресс автоматически не переносятся.

## Обновление

```sh
cd /opt/guild-seekers
sh deploy/backup.sh
git pull --ff-only
docker compose -f compose.yaml -f compose.production.yaml up -d --build
```

## Резервные копии

```sh
cp deploy/guild-backup.service deploy/guild-backup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now guild-backup.timer
sh deploy/backup.sh
```

Копии сохраняются ежедневно в `/var/backups/guild-seekers`, хранятся семь дней.
Это копии на том же VPS: важные копии дополнительно скачивайте на другой компьютер.
Расписание — 03:00 UTC, то есть 06:00 по Москве, плюс случайная задержка до пяти минут.

## Диагностика

```sh
curl -fsS http://127.0.0.1:8000/health
docker compose -f compose.yaml -f compose.production.yaml logs --tail 50 app caddy
systemctl list-timers guild-backup.timer
```
