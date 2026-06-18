"""Phase 1 위험도 스냅샷 러너 (no-touch).

팀원 LightGBM 코드를 import 라이브러리로만 쓰고, 내 config(test=my_test.csv, device=cpu)로
그들의 main.run() 을 호출한다. 그들 파일은 수정하지 않는다(스크래치 복사본에서 실행).

실행: cd analysis/risk_snapshot && python3 run_snapshot.py
출력: scripts/LightGBM_Model/results/test_anomalies.csv (2025-12 ~ 라이브 최신)
"""
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
MODEL = HERE / "scripts" / "LightGBM_Model"

# 내 config: 그들 config.yaml 복사 후 test→my_test, device→cpu, 경로→스크래치 기준
cfg = yaml.safe_load((MODEL / "config.yaml").read_text(encoding="utf-8"))
cfg["data"]["train"] = "data/ai_dataset/train.csv"
cfg["data"]["valid"] = "data/ai_dataset/valid.csv"
cfg["data"]["test"] = "my_test.csv"
cfg["data"]["calendar"] = "data/processed_data/날짜인덱스.csv"
cfg["data"]["bills"] = "data/processed_data/청구서.csv"
cfg["model"]["device"] = "cpu"
my_config = HERE / "my_config.yaml"
my_config.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")

sys.path.insert(0, str(MODEL))
import main as model_main  # noqa: E402

model_main.run(my_config)
