# 운영 서버 설정 (`deploy/`)

NCP 운영 서버(`water-prod`, Ubuntu 24.04)에 실제로 깔려 있는 설정 파일을 그대로 모았습니다. 비밀값이 든 설정 파일(`/etc/water-monitor.env`, `/etc/water-backup.env`)은 깃에 올리지 않고, 항목 이름과 형식만 `*.env.example`에 둡니다.

## 매일 도는 순서

| 시각(KST) | 무엇이 | 하는 일 |
|---|---|---|
| 03:30 | `water-backup.timer` → `water-backup.sh` | DB 사본 + 데이터 폴더 + 지금 화면용 스냅샷 + `data/daily`를 묶어 Object Storage `hanwool-water-backup/daily/<날짜>/`에 올림. 서버에 7일, 스토리지에 180일 보관 |
| 08:00 | 웹 서버(`water-monitor.service`) 안의 수집기 | 아리수 일일 사용량·청구서 수집. 일시 오류는 30분 간격 최대 2번 재시도, 남은 실패는 총괄 관리자에게 메일. 다 끝나면 `settings.collection_auto_settled`에 날짜를 남김 |
| 08:05~ | `water-refresh.timer` → `water-refresh.sh` | 위 표시가 생길 때까지 1분마다 확인 → 승하차 수집(전날 자료가 없으면 10분마다 다시, 최대 1시간) → 모델 갱신 |
| 14:00 | `water-storage.timer` → `water-storage.sh` | 팀원 Object Storage 보관(`back/storage`): 운영 DB 백업과 바뀐 파일을 `hanwool-data/prod/`에 올림. DB 백업은 최근 30개, 화면용 스냅샷은 지금 버전만 남김. 웹 안의 자동 훅은 켜지 않음(아래 '함께 알아 둘 것') |

## 파일과 서버 위치

| 파일 | 서버 위치 | 권한 |
|---|---|---|
| `systemd/water-monitor.service` | `/etc/systemd/system/` | 644 |
| `systemd/water-refresh.service`, `systemd/water-refresh.timer` | `/etc/systemd/system/` | 644 |
| `systemd/water-backup.service`, `systemd/water-backup.timer` | `/etc/systemd/system/` | 644 |
| `systemd/water-storage.service`, `systemd/water-storage.timer` | `/etc/systemd/system/` | 644 |
| `water-refresh.sh`, `water-backup.sh`, `water-storage.sh` | `/usr/local/sbin/` | 755 |
| `water-cli` (운영 설정으로 관리 명령을 water 사용자로 실행) | `/usr/local/sbin/` | 700 |
| `nginx/water-monitor.conf` (HTTPS, 로그인 요청 제한, 8000번으로 전달) | `/etc/nginx/sites-available/water-monitor` | 644 |
| `water-monitor.env.example` | `/etc/water-monitor.env` (값을 채워서) | 600, root |
| `water-backup.env.example` | `/etc/water-backup.env` (값을 채워서) | 600, root |

경로는 지금 서버 기준입니다: 앱 `/home/water/app`(water 사용자), 파이썬 `/home/water/miniforge3/envs/hanul`, 운영 자료 `/var/lib/water-monitor`, 백업 사본 `/var/backups/water-monitor`. 서버를 새로 만들면 같은 경로로 맞추거나 파일 안 경로를 바꿉니다.

## 깔거나 고칠 때 (root)

```sh
cd /home/water/app
install -m 755 deploy/water-refresh.sh deploy/water-backup.sh deploy/water-storage.sh /usr/local/sbin/
install -m 700 deploy/water-cli /usr/local/sbin/
install -m 644 deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now water-monitor water-refresh.timer water-backup.timer water-storage.timer
systemctl list-timers 'water-*'          # 03:30 백업, 08:05 갱신, 14:00 보관이 보이면 된다
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
systemctl stop water-monitor water-refresh.timer water-backup.timer water-storage.timer water-storage.service
mv /var/lib/water-monitor /var/lib/water-monitor.broken-$(date +%F)   # 지우지 않고 옆으로 옮긴다
mkdir -p /var/lib/water-monitor
tar -xzf data.tar.gz -C /var/lib/water-monitor
rm -f /var/lib/water-monitor/.object-storage-index.json   # 다음 14:00 보관이 버킷과 처음부터 다시 대조해 맞춘다
[ -f snapshot.tar.gz ] && tar -xzf snapshot.tar.gz -C /var/lib/water-monitor
gunzip -c app.sqlite3.gz > /var/lib/water-monitor/app.sqlite3
[ -f legacy-daily.tar.gz ] && tar -xzf legacy-daily.tar.gz -C /home/water/app/data && chown -R water:water /home/water/app/data/daily
chown -R water:water /var/lib/water-monitor
chmod 700 /var/lib/water-monitor
chmod 600 /var/lib/water-monitor/app.sqlite3
systemctl start water-monitor water-refresh.timer water-backup.timer
# 되돌린 자료를 확인한 뒤에 켠다(멈춘 사이 14:00가 지났으면 켜자마자 버킷을 되돌린 상태로 맞춘다)
systemctl start water-storage.timer
```
백업한 날 이후에 수집된 자료는 다음 자동 수집이 빠진 날짜를 찾아 다시 채웁니다.

## 함께 알아 둘 것

- 03:30 백업은 날짜별로 되돌리는 용도입니다. 앱 안의 Object Storage 보관 기능(`back/storage`)은 수집 자료 보관과 새 서버 복원용이고, 14:00 `water-storage.sh`가 하루 한 번 돌립니다. 백업 사본은 데이터 폴더 밖에 만들어서 두 기능이 겹치지 않습니다.
- 웹 설정(`/etc/water-monitor.env`)에는 `OBJECT_STORAGE_` 줄을 넣지 않습니다. 이 파일은 08:05 `water-refresh`도 읽어서, 넣으면 웹과 갱신 안의 자동 훅이 켜집니다. 훅은 수집 워커 안에서 시간 제한 없이 돌아서 스토리지가 막히는 날 08:00 수집 마무리(재시도·실패 메일·완료 표시)와 모델 갱신이 몇 시간 밀립니다. 보관은 버킷 `hanwool-data`의 `prod/`를 쓰고(코드 기본값 `mulsaemi`는 팀원 PC 시험용), 키는 03:30 백업용 서브 계정 키를 이 작업에만 넘깁니다.
- 팀원 인수인계 문서(`docs/ncp-object-storage-handoff.md`)의 웹 설정에 넣고 켜기(5-1 3번, 5-4 1번), 기본 접두어 `mulsaemi`, root 셸에서 `python -m back.storage` 실행은 이 서버에서 하지 않습니다. 이 방식에서는 `audit_log`의 `storage_db_backup`이 생기지 않으니, 확인은 `journalctl -u water-storage`와 `water-storage.sh list-backups`로 합니다.
- 보관 명령(`python -m back.storage …`)은 root로 직접 돌리지 않고 `water-storage.sh <명령>`으로 돌립니다(예: `status`, `plan`, `selftest`, `verify`, `list-backups`). root로 돌리면 자료 폴더에 root 소유 잠금·색인 파일이 생겨 보관과 03:30 백업이 깨집니다.
- 새 서버를 버킷에서 되살릴 때는 웹과 타이머를 켜기 전에 `install -d -o water -g water -m 700 /var/lib/water-monitor` → `water-storage.sh restore /var/lib/water-monitor --db`를 실행하고, 출력의 `database`에 `key`가 있고 `failed`가 `[]`인지 봅니다(`skipped_existing`이면 DB를 받지 못한 것). 이미 있는 파일은 덮어쓰지 않으니 웹이 먼저 떠서 `app.sqlite3`가 생겼으면 웹을 멈추고 `app.sqlite3*`를 옆으로 옮긴 뒤 다시 합니다. 돌고 있는 서버에서는 쓰지 않고 `--overwrite`도 쓰지 않습니다. 접두어 `prod`가 들어 있어 팀원 PC 자료와 섞이지 않습니다. 레포 안 옛 수집 폴더(`data/daily`)는 버킷에 없으니 03:30 백업의 `legacy-daily.tar.gz`에서 가져옵니다.
- 운영 DB는 root로 열지 않습니다(DB 옆에 root 소유 파일이 생겨 앱이 망가질 수 있음). 확인할 때는 `sudo -u water sqlite3 -readonly /var/lib/water-monitor/app.sqlite3 "..."`.
- 코드를 반영하는 법: `cd /home/water/app && sudo -u water git pull --ff-only` → 패키지가 바뀌었으면 `sudo -u water /home/water/miniforge3/envs/hanul/bin/python -m pip install -r requirements-dev.txt` → 화면이 바뀌었으면 `su - water -c "cd ~/app && npm ci && npm run build"` → `systemctl restart water-monitor`.
