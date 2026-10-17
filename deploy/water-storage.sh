#!/bin/bash
# 팀원 Object Storage 보관(back/storage)을 하루 한 번 돌린다: 운영 DB 백업 + 바뀐 파일을 hanwool-data/prod/에 올린다. water-storage.timer가 매일 14:00(KST)에 실행한다.
# 웹(water-monitor) 안의 자동 훅은 켜지 않는다. 훅은 수집 워커 안에서 시간 제한 없이 돌아서, 스토리지가 막히면 08:00 수집 마무리와 모델 갱신이 몇 시간 밀린다.
# 접두어 prod는 팀원 PC가 쓰는 코드 기본값 mulsaemi와 나눈 것이다. 키는 03:30 백업용 서브 계정 키를 이 작업에만 넘긴다.
# root가 손으로 실행하면 설정을 읽은 뒤 water 사용자로 다시 실행한다(자료 폴더에 root 소유 파일이 생기면 보관과 03:30 백업이 깨진다).
# 인자를 주면 그 명령만 실행한다. 예: water-storage.sh status | plan | selftest | verify | list-backups
set -euo pipefail
if [ "$(id -u)" -eq 0 ]; then
  set -a; . /etc/water-monitor.env; . /etc/water-backup.env; set +a
  exec runuser -u water -- "$(readlink -f "$0")" "$@"
fi
export OBJECT_STORAGE_ENABLED=true OBJECT_STORAGE_BUCKET=hanwool-data OBJECT_STORAGE_PREFIX=prod
export OBJECT_STORAGE_ACCESS_KEY="$AWS_ACCESS_KEY_ID" OBJECT_STORAGE_SECRET_KEY="$AWS_SECRET_ACCESS_KEY"
PY=/home/water/miniforge3/envs/hanul/bin/python
cd /home/water/app

if [ $# -gt 0 ]; then
  exec "$PY" -m back.storage "$@"
fi
# 지난 실행이 DB 백업 도중 멈추며(3시간 제한 등) 남긴 운영 DB 임시 사본을 지운다
find "$APP_DATA_DIR" -maxdepth 1 -name '.app-backup.*' -mmin +120 -delete || true
rc=0
"$PY" -m back.storage backup-db || rc=1
"$PY" -m back.storage sync || rc=1
exit "$rc"
