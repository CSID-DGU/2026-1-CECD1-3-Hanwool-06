# 운영 서버 설정 (`deploy/`)

NCP 운영 서버(`water-prod`, Ubuntu 24.04)에 실제로 깔려 있는 설정 파일을 그대로 모았습니다. 비밀값이 든 설정 파일(`/etc/water-monitor.env`, `/etc/water-backup.env`)은 깃에 올리지 않고, 항목 이름과 형식만 `*.env.example`에 둡니다.

## 매일 도는 순서

| 시각(KST) | 무엇이 | 하는 일 |
|---|---|---|
| 03:30 | `water-backup.timer` → `water-backup.sh` | DB 사본 + 데이터 폴더 + 지금 화면용 스냅샷 + `data/daily`를 묶어 Object Storage `hanwool-water-backup/daily/<날짜>/`에 올림. 서버에 7일, 스토리지에 180일 보관 |
| 08:00 | 웹 서버(`water-monitor.service`) 안의 수집기 | 아리수 일일 사용량·청구서 수집. 일시 오류는 30분 간격 최대 2번 재시도, 남은 실패는 총괄 관리자에게 메일. 다 끝나면 `settings.collection_auto_settled`에 날짜를 남김 |
| 08:05~ | `water-refresh.timer` → `water-refresh.sh` | 위 표시가 생길 때까지 1분마다 확인 → 승하차 수집(전날 자료가 없으면 10분마다 다시, 최대 1시간) → 모델 갱신 |

## 파일과 서버 위치

| 파일 | 서버 위치 | 권한 |
|---|---|---|
| `systemd/water-monitor.service` | `/etc/systemd/system/` | 644 |
| `systemd/water-refresh.service`, `systemd/water-refresh.timer` | `/etc/systemd/system/` | 644 |
| `systemd/water-backup.service`, `systemd/water-backup.timer` | `/etc/systemd/system/` | 644 |
| `water-refresh.sh`, `water-backup.sh` | `/usr/local/sbin/` | 755 |
| `water-cli` (운영 설정으로 관리 명령을 water 사용자로 실행) | `/usr/local/sbin/` | 700 |
| `nginx/water-monitor.conf` (HTTPS, 로그인 요청 제한, 8000번으로 전달) | `/etc/nginx/sites-available/water-monitor` | 644 |
| `water-monitor.env.example` | `/etc/water-monitor.env` (값을 채워서) | 600, root |
| `water-backup.env.example` | `/etc/water-backup.env` (값을 채워서) | 600, root |

경로는 지금 서버 기준입니다: 앱 `/home/water/app`(water 사용자), 파이썬 `/home/water/miniforge3/envs/hanul`, 운영 자료 `/var/lib/water-monitor`, 백업 사본 `/var/backups/water-monitor`. 서버를 새로 만들면 같은 경로로 맞추거나 파일 안 경로를 바꿉니다.

## 깔거나 고칠 때 (root)

```sh
cd /home/water/app
install -m 755 deploy/water-refresh.sh deploy/water-backup.sh /usr/local/sbin/
install -m 700 deploy/water-cli /usr/local/sbin/
install -m 644 deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now water-monitor water-refresh.timer water-backup.timer
systemctl list-timers 'water-*'          # 03:30 백업, 08:05 갱신이 보이면 된다
```

Nginx(인증서를 받은 뒤):
```sh
install -m 644 deploy/nginx/water-monitor.conf /etc/nginx/sites-available/water-monitor
ln -sf /etc/nginx/sites-available/water-monitor /etc/nginx/sites-enabled/water-monitor
nginx -t && systemctl reload nginx
```
인증서 자동 갱신은 `/etc/crontab`의 한 줄입니다(IP 인증서는 약 6일짜리라 하루 두 번 확인).
```
0 0,12 * * * root /opt/certbot/bin/python -c 'import random; import time; time.sleep(random.random() * 3600)' && certbot renew -q
```

서버에서 이 파일들을 고쳤으면 여기에도 같은 내용으로 올려 둡니다.

## 백업에서 되돌리기 (root)

```sh
set -a; . /etc/water-backup.env; set +a
DAY=<되돌릴 날짜, 예: 2026-10-17>
mkdir -p /root/restore && cd /root/restore
aws --endpoint-url "$S3_ENDPOINT" s3 cp "s3://$BACKUP_BUCKET/daily/$DAY/" . --recursive
systemctl stop water-monitor water-refresh.timer water-backup.timer
mv /var/lib/water-monitor /var/lib/water-monitor.broken-$(date +%F)   # 지우지 않고 옆으로 옮긴다
mkdir -p /var/lib/water-monitor
tar -xzf data.tar.gz -C /var/lib/water-monitor
[ -f snapshot.tar.gz ] && tar -xzf snapshot.tar.gz -C /var/lib/water-monitor
gunzip -c app.sqlite3.gz > /var/lib/water-monitor/app.sqlite3
[ -f legacy-daily.tar.gz ] && tar -xzf legacy-daily.tar.gz -C /home/water/app/data && chown -R water:water /home/water/app/data/daily
chown -R water:water /var/lib/water-monitor
chmod 700 /var/lib/water-monitor
chmod 600 /var/lib/water-monitor/app.sqlite3
systemctl start water-monitor water-refresh.timer water-backup.timer
```
백업한 날 이후에 수집된 자료는 다음 자동 수집이 빠진 날짜를 찾아 다시 채웁니다.

## 함께 알아 둘 것

- 03:30 백업은 날짜별로 되돌리는 용도입니다. 앱 안의 Object Storage 보관 기능(`back/storage`, 기본 꺼짐)은 수집 자료 보관과 새 서버 복원용이고, 켜는 순서는 [`docs/ncp-object-storage-handoff.md`](../docs/ncp-object-storage-handoff.md)에 있습니다. 백업 사본은 데이터 폴더 밖에 만들어서 두 기능이 겹치지 않습니다.
- 운영 DB는 root로 열지 않습니다(DB 옆에 root 소유 파일이 생겨 앱이 망가질 수 있음). 확인할 때는 `sudo -u water sqlite3 -readonly /var/lib/water-monitor/app.sqlite3 "..."`.
- 코드를 반영하는 법: `cd /home/water/app && sudo -u water git pull --ff-only` → 패키지가 바뀌었으면 `sudo -u water /home/water/miniforge3/envs/hanul/bin/python -m pip install -r requirements-dev.txt` → 화면이 바뀌었으면 `su - water -c "cd ~/app && npm ci && npm run build"` → `systemctl restart water-monitor`.
