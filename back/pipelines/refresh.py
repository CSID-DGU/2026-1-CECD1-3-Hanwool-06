"""Refresh private observations and publish a validated, versioned snapshot.

Run from the repository root: python -m back.pipelines.refresh --start YYYY-MM-DD
--end YYYY-MM-DD --water --ridership --bills --model. No flags means no network work.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from back.pipelines.common import RUNTIME, atomic_text, collection_lock, collector_meters, customer_number, today, write_json


def _read_csv(path):
    import pandas as pd
    return pd.read_csv(path, encoding="utf-8-sig", dtype={"고객번호": str})


def build_dataset(output_dir, *, meters, data_root=None, daily_root=None, train_end=None, valid_end=None):
    """Build by customer number, keeping missing ridership distinct from zero."""
    import numpy as np
    import pandas as pd
    data_root = Path(data_root or ROOT / "data")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    mapping = {customer_number(m["customer_number"]): m for m in meters}
    daily = _read_csv(data_root / "processed" / "daily_water_usage.csv").rename(columns={"검침일": "날짜"})
    rides = _read_csv(data_root / "processed" / "ridership.csv").rename(columns={"사용일": "날짜"})
    rides["총승객수"] = rides["승차총승객수"] + rides["하차총승객수"]
    # Legacy rows identify observations by a reviewed CSV alias, never by a fuzzy station match.
    alias = _read_csv(data_root / "billing" / "meter_match.csv")
    name_to_customer = dict(zip(alias["일일CSV파일명"], alias["고객번호"].str.zfill(9)))
    water_parts = [daily[["고객번호", "날짜", "일사용량_톤"]]]
    ride_parts = [rides[["고객번호", "날짜", "승차총승객수", "하차총승객수", "총승객수"]]]
    sources = [data_root / "daily", Path(daily_root or RUNTIME / "daily")]
    for source in dict.fromkeys(sources):
        for path in sorted((source / "water").glob("*.csv")):
            frame = _read_csv(path)
            if frame.empty:
                continue
            if "고객번호" not in frame:
                frame["고객번호"] = frame["역명"].map(name_to_customer)
            if frame["고객번호"].isna().any():
                raise ValueError(f"Unmapped historical water rows in {path.name}")
            frame = frame.rename(columns={"사용일": "날짜", "일사용량(톤)": "일사용량_톤"})
            water_parts.append(frame[["고객번호", "날짜", "일사용량_톤"]])
        for path in sorted((source / "ridership").glob("*.csv")):
            frame = _read_csv(path)
            if not frame.empty:
                ride_parts.append(frame[["고객번호", "날짜", "총승객수"]])
    water = pd.concat(water_parts, ignore_index=True)
    riders = pd.concat(ride_parts, ignore_index=True)
    for frame in (water, riders):
        frame["고객번호"] = frame["고객번호"].map(customer_number)
        frame["날짜"] = pd.to_datetime(frame["날짜"], errors="raise").dt.strftime("%Y-%m-%d")
    water["일사용량_톤"] = pd.to_numeric(water["일사용량_톤"].astype(str).str.replace(",", ""), errors="coerce")
    water = water[water["고객번호"].isin(mapping)].drop_duplicates(["고객번호", "날짜"], keep="last")
    water = water[np.isfinite(water["일사용량_톤"]) & (water["일사용량_톤"] >= 0)]
    riders = riders[riders["고객번호"].isin(mapping)].drop_duplicates(["고객번호", "날짜"], keep="last")
    master = water.merge(riders, on=["고객번호", "날짜"], how="left", validate="one_to_one")
    for target, field in [("역명", "station_name"), ("사업소명", "office_name"), ("고지서_성명", "station_name")]:
        master[target] = master["고객번호"].map(lambda key: mapping[key].get(field) or "")
    dt = pd.to_datetime(master["날짜"])
    master["요일"] = dt.dt.weekday.map(dict(enumerate("월화수목금토일")))
    master["일유형"] = pd.NA
    master = master.sort_values(["고객번호", "날짜"]).reset_index(drop=True)
    # Preserve established evaluation cutoffs unless explicitly retraining with new boundaries.
    train_end = train_end or str(_read_csv(data_root / "ml_dataset" / "train.csv")["날짜"].max())
    valid_end = valid_end or str(_read_csv(data_root / "ml_dataset" / "valid.csv")["날짜"].max())
    if train_end >= valid_end:
        raise ValueError("train_end must precede valid_end")
    splits = {"train": master[master["날짜"] <= train_end],
              "valid": master[(master["날짜"] > train_end) & (master["날짜"] <= valid_end)],
              "test": master[master["날짜"] > valid_end]}
    train_counts = splits["train"].groupby("고객번호").size()
    valid_counts = splits["valid"].groupby("고객번호").size()
    eligible = {key for key in mapping if train_counts.get(key, 0) >= 90 and valid_counts.get(key, 0) >= 14}
    withheld = [{"customer_number": key, "reason": "학습 90일 및 검증 14일의 이력이 필요합니다",
                 "train_days": int(train_counts.get(key, 0)), "valid_days": int(valid_counts.get(key, 0))}
                for key in mapping if key not in eligible]
    atomic_text(output_dir / "master.csv", master.to_csv(index=False), encoding="utf-8-sig")
    for name, frame in splits.items():
        frame = frame[frame["고객번호"].isin(eligible)]
        atomic_text(output_dir / f"{name}.csv", frame.to_csv(index=False), encoding="utf-8-sig")
    return master, riders, withheld, eligible


def build_calendar(master, output):
    import holidays
    import pandas as pd
    dates = pd.date_range(master["날짜"].min(), master["날짜"].max())
    ko = holidays.KR(years=range(dates[0].year, dates[-1].year + 1), language="ko")
    frame = pd.DataFrame({"날짜": dates.strftime("%Y-%m-%d"), "월": dates.month,
        "요일_숫자": dates.weekday, "주말": (dates.weekday >= 5).astype(int),
        "공휴일": [int(d.date() in ko) for d in dates]})
    frame["휴무일"] = ((frame["주말"] == 1) | (frame["공휴일"] == 1)).astype(int)
    frame["징검다리"] = ((frame["휴무일"] == 0) & (frame["휴무일"].shift(1) == 1) & (frame["휴무일"].shift(-1) == 1)).astype(int)
    atomic_text(output, frame.to_csv(index=False), encoding="utf-8-sig")


def publish_snapshot(master, riders, *, output_dir, anomalies=None, withheld=(), previous_risk=None):
    import math
    daily = {}
    for source, field, value in [(master, "usage", "일사용량_톤"), (riders, "ridership", "총승객수")]:
        for key, group in source.groupby("고객번호", observed=True):
            entry = daily.setdefault(customer_number(key), {"usage": [], "ridership": []})
            entry[field] = [{"date": str(row["날짜"]), "value": float(row[value])}
                            for _, row in group.sort_values("날짜").iterrows() if math.isfinite(float(row[value]))]
    risk = previous_risk or {}
    if anomalies is not None:
        risk = {}
        for _, row in anomalies.iterrows():
            if row["심각도"] == "자료부족" or not math.isfinite(float(row["deviation_score"])):
                continue
            key = customer_number(row["고객번호"])
            risk.setdefault(key, []).append({"date": str(row["날짜"])[:10],
                "actual": float(row["일사용량_톤"]), "pred": float(row["predicted_ton"]),
                "residual": float(row["error_ton"]), "z": float(row["deviation_score"]),
                "severity": row["심각도"], "dir": row["방향"] if isinstance(row["방향"], str) else "",
                "err": bool(row["likely_data_error"])})
    return publish_data(daily, risk, output_dir=output_dir, withheld=withheld)


def publish_data(daily, risk, *, output_dir, withheld=()):
    output_dir = Path(output_dir)
    version = f"versions/{uuid.uuid4().hex}"
    destination = output_dir / version
    write_json(destination / "daily.json", daily)
    write_json(destination / "risk.json", risk)
    latest = lambda field: max((r["date"] for d in daily.values() for r in d[field]), default=None)
    manifest = {"published": True, "directory": version, "generated_at": datetime.now(timezone.utc).isoformat(),
                "water_as_of": latest("usage"), "ridership_as_of": latest("ridership"),
                "risk_as_of": max((r["date"] for values in risk.values() for r in values), default=None),
                "withheld": list(withheld), "counts": {"daily_customers": len(daily), "risk_customers": len(risk)}}
    # A single atomic pointer publishes both files; failed generation retains the old version.
    write_json(output_dir / "manifest.json", manifest)
    # Keep every version from the last day plus at least the latest three.
    # Readers have a full day to finish using an older manifest pointer.
    try:
        versions = [p for p in (output_dir / "versions").iterdir()
                    if not p.is_symlink() and p.is_dir() and re.fullmatch(r"[0-9a-f]{32}", p.name)]
        versions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for old in versions[3:]:
            if old.name != destination.name and old.stat().st_mtime < time.time() - 86400:
                shutil.rmtree(old)
    except OSError:
        pass  # Cleanup failure must not invalidate a published snapshot.
    return manifest


def refresh_bills(start, end, meters, runtime):
    import pandas as pd
    from back.scripts.billing_etl.crawl_bills import collect_bills
    from back.scripts.dataset_etl.build_clean_dataset import build_bills_bimonthly
    raw_dir = runtime / "raw" / "billing_i121"
    report = collect_bills(start_ym=str(start)[:7], end_ym=str(end)[:7],
        mkeys=[m["customer_number"] for m in collector_meters(meters, daily=False)],
        customer_names={m['customer_number']: m.get('metadata', {}).get('arisu_customer_name', '') for m in meters},
        cache_dir=raw_dir / "i121_cache", out_dir=raw_dir / "i121_bills")
    if report["errors"]:
        raise RuntimeError("Some bill requests failed; raw successes preserved, derived bills unchanged")
    path = raw_dir / "i121_bills" / "bills_long.csv"
    if not path.exists():
        return report
    # Notice numbers are identifiers; blank regular notices and leading zeroes must survive CSV.
    raw = pd.read_csv(path, encoding="utf-8-sig", dtype={"mkey": str, "notice_number": str}, keep_default_na=False)
    from back.api import db
    from back.api.import_data import upsert_bill_summaries
    with db.connect() as conn:
        upsert_bill_summaries(conn, raw.where(pd.notna(raw), None).to_dict("records"))
    raw = raw[raw["gubun"] == "정기분"].rename(columns={"mkey": "고객번호", "napgi": "납기일", "total_usage_ton": "총사용량_톤", "bugwa_amount_won": "부과금액_원"})
    metadata = {customer_number(m["customer_number"]): m for m in meters}
    raw["고객번호"] = raw["고객번호"].map(customer_number)
    raw = raw[raw["고객번호"].isin(metadata)]
    for target, field in [("역명", "station_name"), ("영업사업소", "office_name"), ("용도", "purpose")]:
        raw[target] = raw["고객번호"].map(lambda key: metadata[key].get(field))
    old = _read_csv(ROOT / "data" / "billing" / "bills_clean.csv")
    old["고객번호"] = old["고객번호"].map(customer_number)
    merged = pd.concat([old, raw], ignore_index=True).drop_duplicates(["고객번호", "납기일"], keep="last")
    for target, field in [("역명", "station_name"), ("영업사업소", "office_name"), ("용도", "purpose")]:
        merged[target] = merged["고객번호"].map(lambda key: metadata.get(key, {}).get(field)).fillna(merged[target])
    clean_path = runtime / "processed" / "bills_clean.csv"
    atomic_text(clean_path, merged.to_csv(index=False), encoding="utf-8-sig")
    labels = pd.DataFrame([{"고객번호": k, "역명": m["station_name"]} for k, m in metadata.items()])
    result = build_bills_bimonthly(clean_path, meter_labels=labels)
    atomic_text(runtime / "processed" / "water_bills.csv", result.to_csv(index=False), encoding="utf-8-sig")
    return report


def run(args):
    with collection_lock(args.runtime_dir):
        return _run(args)


def _run(args):
    import pandas as pd
    import yaml
    from back.api.catalog import collector_meters as registered
    meters = registered()
    runtime = Path(args.runtime_dir)
    runtime.mkdir(parents=True, exist_ok=True)
    report = {"start": str(args.start), "end": str(args.end), "steps": {}, "errors": []}
    if args.start > args.end or args.end >= today():
        raise ValueError("Collect dates through yesterday; start must not exceed end")
    if args.water:
        from back.pipelines.daily_water.scraper import scrape_range
        try:
            result = scrape_range(args.start, args.end, meters=meters, out_dir=runtime / "daily" / "water")
            report["steps"]["water"] = result
            if any(r["errors"] for r in result):
                report["errors"].append("water collection failed")
        except Exception as exc:
            report["errors"].append(f"water: {type(exc).__name__}")
    if args.ridership:
        from back.pipelines.daily_ridership.scraper import scrape
        report["steps"]["ridership"] = []
        day = args.start
        while day <= args.end:
            try:
                path = scrape(day, meters=meters, out_dir=runtime / "daily" / "ridership")
                status_path = runtime / "daily" / "ridership" / f"{day}.status.json"
                status = json.loads(status_path.read_text()) if status_path.exists() else {"date": str(day), "status": "collected" if path else "pending"}
                report["steps"]["ridership"].append(status)
            except Exception as exc:
                report["errors"].append(f"ridership {day}: {type(exc).__name__}")
            day += timedelta(days=1)
    if args.bills:
        try:
            report["steps"]["bills"] = refresh_bills(args.start, args.end, meters, runtime)
        except Exception as exc:
            report["errors"].append(f"bills: {type(exc).__name__}")
    if report["errors"]:
        write_json(runtime / "refresh_report.json", report)
        return 1
    if args.model or args.water or args.ridership:
        try:
            dataset_dir = runtime / "dataset"
            active = collector_meters(meters)
            master, riders, withheld, eligible = build_dataset(dataset_dir, meters=active,
                daily_root=runtime / "daily", train_end=args.train_end, valid_end=args.valid_end)
            if master.empty:
                raise ValueError("No valid water observations available")
            build_calendar(master, dataset_dir / "calendar.csv")
            cfg = yaml.safe_load((ROOT / "back" / "ml" / "lightgbm" / "config.yaml").read_text())
            cfg["data"] = {split: str((dataset_dir / f"{split}.csv").resolve()) for split in ["train", "valid", "test"]}
            cfg["data"]["calendar"] = str((dataset_dir / "calendar.csv").resolve())
            bills_path = runtime / "processed" / "water_bills.csv"
            cfg["data"]["bills"] = str((bills_path if bills_path.exists() else ROOT / "data" / "processed" / "water_bills.csv").resolve())
            cfg["model"]["device"] = "cpu"
            cfg["model"]["n_jobs"] = args.jobs
            cfg["save_plot"] = False
            config_path = dataset_dir / "config.yaml"
            atomic_text(config_path, yaml.safe_dump(cfg, allow_unicode=True))
            previous_risk = None
            anomalies = None
            if args.model and eligible and not _read_csv(dataset_dir / "test.csv").empty:
                from back.ml.lightgbm.main import run as train
                metrics = train(config_path, runtime / "model")
                anomalies = _read_csv(runtime / "model" / "test_anomalies.csv")
                if len(anomalies) != metrics["test"]["n_samples"]:
                    raise ValueError("Saved prediction count differs from model evaluation")
            elif args.model:
                anomalies = pd.DataFrame()
            else:
                manifest_path = runtime / "snapshot" / "manifest.json"
                if manifest_path.exists():
                    old_manifest = json.loads(manifest_path.read_text())
                    snapshot_root = (runtime / "snapshot").resolve()
                    old_dir = (snapshot_root / old_manifest.get("directory", ".")).resolve()
                    if old_dir != snapshot_root and snapshot_root not in old_dir.parents:
                        raise ValueError("Invalid previous snapshot directory")
                    risk_path = old_dir / "risk.json"
                    if risk_path.exists():
                        previous_risk = json.loads(risk_path.read_text())
                if previous_risk is None:
                    from back.api.catalog import data_sources
                    _, previous_risk = data_sources()
            report["steps"]["snapshot"] = publish_snapshot(master, riders, output_dir=runtime / "snapshot",
                anomalies=anomalies, withheld=withheld, previous_risk=previous_risk)
        except Exception as exc:
            report["errors"].append(f"model: {type(exc).__name__}: {exc}")
    write_json(runtime / "refresh_report.json", report)
    return 1 if report["errors"] else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=today() - timedelta(days=5))
    parser.add_argument("--end", type=date.fromisoformat, default=today() - timedelta(days=1))
    for flag in ["water", "ridership", "bills", "model", "all"]:
        parser.add_argument(f"--{flag}", action="store_true")
    parser.add_argument("--runtime-dir", type=Path, default=RUNTIME)
    parser.add_argument("--train-end", type=str)
    parser.add_argument("--valid-end", type=str)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if args.all:
        args.water = args.ridership = args.bills = args.model = True
    if not any([args.water, args.ridership, args.bills, args.model]):
        parser.error("Choose at least one of --water --ridership --bills --model (or --all)")
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
