"""
Rebuild koi_lightcurves/manifest.csv after lightcurve_ananya.py crashed on its
final print() (stdout closed) before writing the manifest. The FITS data is all
on disk; this reconstructs the manifest from disk + remaining_targets.csv.
"""

import os
import re
import pandas as pd

OUTPUT_DIR = "koi_lightcurves"
CSV = "remaining_targets.csv"

base_dir = os.path.join(OUTPUT_DIR, "mastDownload", "Kepler")
downloaded = set()
for folder in os.listdir(base_dir):
    m = re.search(r"kplr0*(\d+)", folder)
    if m:
        downloaded.add(int(m.group(1)))
print(f"Distinct kepids with downloaded data on disk: {len(downloaded)}")

df = pd.read_csv(CSV)
rows = []
for _, row in df.iterrows():
    kepid = int(row["kepid"])
    ok = kepid in downloaded
    rows.append({
        "kepid": kepid,
        "kepoi_name": row.get("kepoi_name", str(kepid)),
        "status": "ok" if ok else "missing",
        "koi_period": row["koi_period"],
        "koi_time0bk": row["koi_time0bk"],
        "koi_duration": row["koi_duration"],
        "label": row["label"],
    })

manifest_df = pd.DataFrame(rows)
out = os.path.join(OUTPUT_DIR, "manifest.csv")
manifest_df.to_csv(out, index=False)

n_ok = (manifest_df["status"] == "ok").sum()
print(f"Wrote {out}")
print(f"ok: {n_ok}/{len(manifest_df)}")
print(manifest_df["status"].value_counts())
missing = manifest_df.loc[manifest_df["status"] == "missing", "kepid"].tolist()
if missing:
    print(f"Missing kepids: {missing}")
