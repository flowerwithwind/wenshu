"""下载医院(SQLite)+物流(MySQL)并注册数据源"""
from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

TMP = BACKEND / "data" / "_kaggle_dl"


def ensure_token() -> None:
    if not os.environ.get("KAGGLE_API_TOKEN"):
        tok = None
        try:
            # Windows machine env already loaded externally usually
            import subprocess

            # best-effort: leave to caller
            pass
        except Exception:
            pass
        if not os.environ.get("KAGGLE_API_TOKEN"):
            print("WARN: KAGGLE_API_TOKEN not in process env", flush=True)


def download(ref: str, subdir: str) -> Path:
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    out = TMP / subdir
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    print(f"download {ref} -> {out}", flush=True)
    api.dataset_download_files(ref, path=str(out), unzip=True)
    # unzip any remaining zips
    for z in out.rglob("*.zip"):
        with zipfile.ZipFile(z, "r") as zf:
            zf.extractall(out)
    return out


def find_csvs(root: Path) -> list[Path]:
    return sorted([p for p in root.rglob("*.csv") if p.is_file()])


def main() -> int:
    ensure_token()
    from app.datasources.manager import create_record, list_datasource_records, delete_record
    from app.datasources.registry import invalidate_datasource_cache, get_datasource
    from app.services.ds_import import import_file_to_datasource, list_tables

    # ---- 医院 -> SQLite ----
    hosp_dir = download("kanakbaghel/hospital-management-dataset", "hospital")
    # 清理旧同名
    for r in list(list_datasource_records()):
        if r.get("name") == "医院管理 (SQLite)":
            delete_record(r["id"])
            invalidate_datasource_cache(r["id"])

    hosp = create_record(
        {
            "name": "医院管理 (SQLite)",
            "type": "sqlite",
            "description": "Kaggle Hospital Management：patients/doctors/appointments/treatments/billing",
            "is_default": False,
        }
    )
    hosp_id = hosp["id"]
    print("created hospital ds", hosp_id, flush=True)
    for csv in find_csvs(hosp_dir):
        tname = csv.stem.lower().replace(" ", "_")
        print(f"  import {csv.name} -> {tname}", flush=True)
        import_file_to_datasource(hosp_id, str(csv), tname)
    print("hospital tables", list_tables(hosp_id), flush=True)

    # ---- 物流 -> MySQL ----
    mysql_password = os.environ.get("MYSQL_PASSWORD", "")
    mysql_user = os.environ.get("MYSQL_USER", "root")
    if not mysql_password:
        print("请设置环境变量 MYSQL_PASSWORD", flush=True)
        return 1
    from sqlalchemy import create_engine, text

    eng = create_engine(
        f"mysql+pymysql://{mysql_user}:{mysql_password}@127.0.0.1:3306/?charset=utf8mb4",
        pool_pre_ping=True,
    )
    with eng.begin() as conn:
        conn.execute(
            text(
                "CREATE DATABASE IF NOT EXISTS logistics_ops "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
        # 清空旧表：重建库
        conn.execute(text("DROP DATABASE IF EXISTS logistics_ops"))
        conn.execute(
            text(
                "CREATE DATABASE logistics_ops "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
    print("mysql logistics_ops ready", flush=True)

    log_dir = download("yogape/logistics-operations-database", "logistics")
    for r in list(list_datasource_records()):
        if r.get("name") == "物流运营 (MySQL)" or r.get("database") == "logistics_ops":
            delete_record(r["id"])
            invalidate_datasource_cache(r["id"])

    log_ds = create_record(
        {
            "name": "物流运营 (MySQL)",
            "type": "mysql",
            "description": "Kaggle Logistics Operations：trips/loads/drivers/trucks/routes 等多表",
            "host": "127.0.0.1",
            "port": 3306,
            "database": "logistics_ops",
            "username": mysql_user,
            "password": mysql_password,
            "is_default": False,
        }
    )
    log_id = log_ds["id"]
    print("created logistics ds", log_id, flush=True)
    for csv in find_csvs(log_dir):
        # skip schema text-like if any
        tname = csv.stem.lower().replace(" ", "_")
        print(f"  import {csv.name} -> {tname}", flush=True)
        try:
            import_file_to_datasource(log_id, str(csv), tname)
        except Exception as e:
            print(f"  SKIP {csv.name}: {e}", flush=True)
    print("logistics tables", list_tables(log_id), flush=True)

    # 验证 JOIN
    ds_h = get_datasource(hosp_id)
    rows, cols = ds_h.execute_sql(
        "SELECT d.specialization, COUNT(*) AS n "
        "FROM appointments a JOIN doctors d ON a.doctor_id = d.doctor_id "
        "GROUP BY d.specialization ORDER BY n DESC LIMIT 5"
    )
    print("hospital join sample", cols, rows, flush=True)

    ds_l = get_datasource(log_id)
    # 尝试常见列名
    schema = ds_l.get_schema_info()
    print("logistics schema preview:\n", schema[:800], flush=True)
    try:
        rows2, cols2 = ds_l.execute_sql(
            "SELECT COUNT(*) AS c FROM trips"
        )
        print("logistics trips count", rows2, flush=True)
    except Exception as e:
        print("logistics sample query fail", e, flush=True)

    # 清理下载
    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)
        print("cleaned download tmp", flush=True)

    print("IMPORT_KAGGLE_DONE", flush=True)
    print("HOSPITAL_DS", hosp_id, flush=True)
    print("LOGISTICS_DS", log_id, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
