#!/usr/bin/env python3
"""
download_dataset.py — fetch the 9 raw Olist CSVs (~140 MB) into data/raw/.

Tries a list of public GitHub mirrors of the Kaggle 'Brazilian E-Commerce by Olist'
dataset (https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) until one works.
Skips files that already exist and have a sane size.
"""

import shutil
import sys
import urllib.request
from pathlib import Path

FILES = [
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
    "olist_geolocation_dataset.csv",
]

MIRRORS = [
    "https://raw.githubusercontent.com/Ajandaghian/olist-ecommerce-etl-pipeline/main/data/raw",
    "https://raw.githubusercontent.com/Anshukun888/olist-ecommerce-analysis/main/data/raw",
]

EXPECTED_MIN = {
    "olist_orders_dataset.csv": 10_000_000,
    "olist_order_items_dataset.csv": 10_000_000,
    "olist_order_payments_dataset.csv": 4_000_000,
    "olist_order_reviews_dataset.csv": 10_000_000,
    "olist_customers_dataset.csv": 6_000_000,
    "olist_products_dataset.csv": 1_000_000,
    "olist_sellers_dataset.csv": 100_000,
    "product_category_name_translation.csv": 1_000,
    "olist_geolocation_dataset.csv": 30_000_000,
}

OUT = Path(__file__).resolve().parents[1] / "data" / "raw"


def fetch(url: str, dest: Path) -> bool:
    tmp = dest.with_suffix(".part")
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        if tmp.stat().st_size >= EXPECTED_MIN.get(dest.name, 1):
            tmp.replace(dest)
            return True
        tmp.unlink(missing_ok=True)
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"    failed: {exc}")
        tmp.unlink(missing_ok=True)
        return False


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ok = 0
    for name in FILES:
        dest = OUT / name
        if dest.exists() and dest.stat().st_size >= EXPECTED_MIN.get(name, 1):
            print(f"[skip] {name} already present ({dest.stat().st_size:,} bytes)")
            ok += 1
            continue
        for base in MIRRORS:
            print(f"[get ] {name}  <-  {base[:60]}...")
            if fetch(f"{base}/{name}", dest):
                print(f"[ ok ] {name} {dest.stat().st_size:,} bytes")
                ok += 1
                break
        else:
            print(f"[FAIL] {name} from all mirrors")
    print(f"\n{ok}/{len(FILES)} files ready in {OUT}")
    return 0 if ok == len(FILES) else 1


if __name__ == "__main__":
    sys.exit(main())
