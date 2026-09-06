"""
download_koi_lightcurves.py

Pre-downloads Kepler light curve FITS files for a sample of KOI targets,
so they can be uploaded to Kaggle as a Dataset and used without hitting
MAST from within the Kaggle notebook.

Usage:
    python download_koi_lightcurves.py

Requires:
    pip install lightkurve pandas tqdm
"""

import os
import socket
import re
import time
import pandas as pd
import lightkurve as lk
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---- Config ----
KOI_CSV_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=select+*+from+cumulative&format=csv"
OUTPUT_DIR = "koi_lightcurves"
N_SAMPLES = 1700          # how many stars to download
MAX_WORKERS = 6          # concurrent download threads (keep modest to avoid rate-limiting)
TIMEOUT_SEC = 45         # per-request network timeout
RANDOM_STATE = 42        # match the random_state used in your Kaggle notebook's sampling

socket.setdefaulttimeout(TIMEOUT_SEC)


def load_and_filter_koi_table():
    print("Downloading KOI cumulative table...")
    koi_df = pd.read_csv(KOI_CSV_URL)

    df = koi_df.copy()
    df = df[df["koi_disposition"].isin(["CONFIRMED", "CANDIDATE", "FALSE POSITIVE"])]
    df["label"] = (df["koi_disposition"] != "FALSE POSITIVE").astype(int)

    feature_cols = ["koi_period", "koi_duration", "koi_depth", "koi_model_snr", "koi_num_transits"]
    df = df.dropna(subset=feature_cols + ["label", "kepid", "koi_time0bk"])

    print(f"Filtered KOI table: {df.shape[0]} usable rows")
    return df


def download_one_target(row, output_dir):
    """
    Downloads and saves the FITS light curve for a single KOI target.
    Returns a dict describing success/failure, used for building a manifest.
    """
    kepid = row["kepid"]
    kepoi_name = row.get("kepoi_name", str(kepid))

    try:
        search_result = lk.search_lightcurve(f"KIC {kepid}", mission="Kepler", author="Kepler")
        if len(search_result) == 0:
            return {"kepid": kepid, "kepoi_name": kepoi_name, "status": "no_data"}

        lc_collection = search_result.download_all(download_dir=output_dir)
        if lc_collection is None or len(lc_collection) == 0:
            return {"kepid": kepid, "kepoi_name": kepoi_name, "status": "download_failed"}

        return {
            "kepid": kepid,
            "kepoi_name": kepoi_name,
            "status": "ok",
            "koi_period": row["koi_period"],
            "koi_time0bk": row["koi_time0bk"],
            "koi_duration": row["koi_duration"],
            "label": row["label"],
        }

    except Exception as e:
        return {"kepid": kepid, "kepoi_name": kepoi_name, "status": f"error: {str(e)[:100]}"}


def get_already_downloaded_kepids(output_dir):
    base_dir = os.path.join(output_dir, "mastDownload", "Kepler")
    if not os.path.exists(base_dir):
        return set()

    downloaded = set()
    for folder in os.listdir(base_dir):
        match = re.search(r"kplr0*(\d+)", folder)  # more permissive: just look for kplr followed by digits, strip leading zeros
        if match:
            downloaded.add(int(match.group(1)))
    return downloaded



def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    remaining_df = pd.read_csv("remaining_targets.csv")  # this is "remaining_targets_other.csv" renamed
    print(f"Downloading {len(remaining_df)} remaining targets")

    manifest = []
    start = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(download_one_target, row, OUTPUT_DIR): row["kepid"]
            for _, row in remaining_df.iterrows()
        }

        for future in tqdm(as_completed(futures), total=len(futures), desc="Downloading"):
            try:
                result = future.result(timeout=60)
            except Exception as e:
                result = {"kepid": futures[future], "status": f"timeout_or_error: {str(e)[:100]}"}
            manifest.append(result)

    elapsed = time.time() - start
    print(f"\nDone in {elapsed/60:.1f} minutes.")

    manifest_df = pd.DataFrame(manifest)
    manifest_df.to_csv(os.path.join(OUTPUT_DIR, "manifest.csv"), index=False)

    n_ok = (manifest_df["status"] == "ok").sum()
    print(f"Successful downloads: {n_ok}/{len(manifest_df)}")


if __name__ == "__main__":
    main()
