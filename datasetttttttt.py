# imports
import numpy as np
import pandas as pd
import lightkurve as lk
from wotan import flatten
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm  # non-notebook version locally
import os, re

# functions needed:
def extract_kepid_from_folder(folder_name):
    match = re.search(r"kplr(\d+)_lc", folder_name)
    if match:
        return int(match.group(1))
    return None

def preprocess_lightcurve(lc, window_length=0.5, sigma=5):
    lc_clean = lc.remove_nans()
    time = lc_clean.time.value
    flux = lc_clean.flux.value

    # sigma clip
    flux_clipped = np.copy(flux)
    med = np.nanmedian(flux_clipped)
    std = np.nanstd(flux_clipped)
    mask = np.abs(flux_clipped - med) < sigma * std
    time_clipped = time[mask]
    flux_clipped = flux_clipped[mask]

    # detrend
    flux_flat, trend = flatten(
        time_clipped, flux_clipped,
        window_length=window_length,
        method="biweight",
        return_trend=True
    )

    # wotan can leave NaNs near gaps/edges -- strip them out before BLS ever sees this
    finite_mask = np.isfinite(flux_flat)
    time_clipped = time_clipped[finite_mask]
    flux_flat = flux_flat[finite_mask]
    trend = trend[finite_mask]

    return time_clipped, flux_flat, trend

def make_global_local_views(time, flux, period, t0, duration, global_bins=201, local_bins=61):
    """
    Bins a phase-folded light curve into fixed-length global and local views
    for CNN input, following the AstroNet-style representation.
    """
    phase = ((time - t0 + 0.5 * period) % period) / period - 0.5
    order = np.argsort(phase)
    phase_sorted = phase[order]
    flux_sorted = flux[order]

    # global view: bin the full phase range [-0.5, 0.5]
    global_bin_edges = np.linspace(-0.5, 0.5, global_bins + 1)
    global_view = np.full(global_bins, np.nan)
    for i in range(global_bins):
        mask = (phase_sorted >= global_bin_edges[i]) & (phase_sorted < global_bin_edges[i+1])
        if mask.sum() > 0:
            global_view[i] = np.nanmedian(flux_sorted[mask])

    # fill empty bins via interpolation
    nan_mask = np.isnan(global_view)
    if nan_mask.any() and not nan_mask.all():
        global_view[nan_mask] = np.interp(
            np.flatnonzero(nan_mask), np.flatnonzero(~nan_mask), global_view[~nan_mask]
        )

    # local view: zoom into +/- 2x transit duration around phase 0
    local_half_width = 2 * (duration / period)
    local_bin_edges = np.linspace(-local_half_width, local_half_width, local_bins + 1)
    local_view = np.full(local_bins, np.nan)
    for i in range(local_bins):
        mask = (phase_sorted >= local_bin_edges[i]) & (phase_sorted < local_bin_edges[i+1])
        if mask.sum() > 0:
            local_view[i] = np.nanmedian(flux_sorted[mask])

    nan_mask = np.isnan(local_view)
    if nan_mask.any() and not nan_mask.all():
        local_view[nan_mask] = np.interp(
            np.flatnonzero(nan_mask), np.flatnonzero(~nan_mask), local_view[~nan_mask]
        )

    return global_view, local_view

def load_local_lightcurve(kepid, base_dir="koi-lightcurves/koi_lightcurves/mastDownload/Kepler"):
    matching_folders = [f for f in os.listdir(base_dir) if f"kplr{kepid:09d}" in f]
    # prefer long-cadence folders; the merged set also contains short-cadence (_sc_) dirs
    lc_folders = [f for f in matching_folders if "_lc_" in f]
    matching_folders = lc_folders or matching_folders
    if not matching_folders:
        return None

    folder_path = os.path.join(base_dir, matching_folders[0])
    fits_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith(".fits")]

    if not fits_files:
        return None

    lc_collection = lk.LightCurveCollection([lk.read(f) for f in fits_files])
    lc = lc_collection.stitch()
    return lc

def process_local_target(args):
    idx, kepid, koi_period, koi_time0bk, koi_duration, label, base_dir, global_bins, local_bins = args
    try:
        lc = load_local_lightcurve(kepid, base_dir=base_dir)
        if lc is None:
            return None

        time_c, flux_f, _ = preprocess_lightcurve(lc, window_length=2.0)
        period = koi_period
        t0 = koi_time0bk
        duration = koi_duration / 24.0

        g_view, l_view = make_global_local_views(
            time_c, flux_f, period, t0, duration,
            global_bins=global_bins, local_bins=local_bins
        )

        if np.isnan(g_view).any() or np.isnan(l_view).any():
            return None

        return (idx, g_view, l_view, label)  # <-- carry the original index through

    except Exception:
        return None

def process_local_target_with_reason(args):
    idx, kepid, koi_period, koi_time0bk, koi_duration, label, base_dir, global_bins, local_bins = args
    try:
        lc = load_local_lightcurve(kepid, base_dir=base_dir)
        if lc is None:
            return (idx, None, "no_local_file")

        time_c, flux_f, _ = preprocess_lightcurve(lc, window_length=2.0)

        if len(time_c) < 50:
            return (idx, None, "too_few_points")

        period = koi_period
        t0 = koi_time0bk
        duration = koi_duration / 24.0

        g_view, l_view = make_global_local_views(
            time_c, flux_f, period, t0, duration,
            global_bins=global_bins, local_bins=local_bins
        )

        if np.isnan(g_view).any() or np.isnan(l_view).any():
            return (idx, None, "nan_in_view")

        return (idx, (g_view, l_view, label), "ok")

    except Exception as e:
        return (idx, None, f"exception: {type(e).__name__}: {str(e)[:80]}")

def build_cnn_dataset_local_parallel(downloaded_df, base_dir="koi-lightcurves/koi_lightcurves/mastDownload/Kepler",
                                       global_bins=201, local_bins=61, n_workers=8):
    args_list = [
        (idx, row["kepid"], row["koi_period"], row["koi_time0bk"], row["koi_duration"], row["label"],
         base_dir, global_bins, local_bins)
        for idx, row in downloaded_df.iterrows()
    ]

    successful_indices = []
    global_views, local_views, labels = [], [], []

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = [executor.submit(process_local_target, args) for args in args_list]

        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing local light curves (parallel)"):
            result = future.result()
            if result is not None:
                idx, g_view, l_view, label = result
                successful_indices.append(idx)
                global_views.append(g_view)
                local_views.append(l_view)
                labels.append(label)

    print(f"Succeeded: {len(labels)} / {len(args_list)}")

    X_global = np.array(global_views)[..., np.newaxis]
    X_local = np.array(local_views)[..., np.newaxis]
    y = np.array(labels)

    # this is now correctly aligned to X_global/X_local/y, regardless of completion order
    aligned_df = downloaded_df.loc[successful_indices].reset_index(drop=True)

    return X_global, X_local, y, aligned_df

def prepare_koi_training_data_v2(koi_df, exclude_kepids=None):
    df = koi_df.copy()
    df = df[df["koi_disposition"].isin(["CONFIRMED", "CANDIDATE", "FALSE POSITIVE"])]
    df["label"] = (df["koi_disposition"] != "FALSE POSITIVE").astype(int)

    if exclude_kepids is not None:
        df = df[~df["kepid"].isin(exclude_kepids)]

    feature_cols = ["koi_period", "koi_duration", "koi_depth", "koi_model_snr", "koi_num_transits"]
    df = df.dropna(subset=feature_cols + ["label"])

    X = df[feature_cols]
    y = df["label"]
    return X, y, df

def main():
    koi_url = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=select+*+from+cumulative&format=csv"
    koi_df = pd.read_csv(koi_url)

    # same filtering/exclusion logic as your Kaggle notebook
    demo_kepids = koi_df[koi_df["kepler_name"].str.contains("Kepler-90", na=False)]["kepid"].unique().tolist()
    X_v2, y_v2, koi_clean_v2 = prepare_koi_training_data_v2(koi_df, exclude_kepids=demo_kepids)

    # rebuild downloaded_df from your local folder, same logic as before
    base_dir = "koi_lightcurves/mastDownload/Kepler"
    star_folders = os.listdir(base_dir)
    downloaded_kepids = [extract_kepid_from_folder(f) for f in star_folders if extract_kepid_from_folder(f) is not None]
    downloaded_df = koi_clean_v2[koi_clean_v2["kepid"].isin(downloaded_kepids)].copy()
    print(f"folders: {len(star_folders)}, distinct kepids matched to KOI table: {downloaded_df['kepid'].nunique()}, "
          f"KOI rows to process: {len(downloaded_df)}")

    n_workers = min(10, os.cpu_count())  # use however many real cores you have

    X_global_mast, X_local_mast, y_mast, aligned_df_mast = build_cnn_dataset_local_parallel(
        downloaded_df, base_dir=base_dir, n_workers=n_workers
    )

    np.save("X_global_mast.npy", X_global_mast)
    np.save("X_local_mast.npy", X_local_mast)
    np.save("y_mast.npy", y_mast)
    aligned_df_mast.to_csv("aligned_df_mast.csv", index=False)
    print(f"saved: X_global={X_global_mast.shape}, X_local={X_local_mast.shape}, y={y_mast.shape}, "
          f"rows={len(aligned_df_mast)}, positives={int(y_mast.sum())}")


if __name__ == "__main__":
    main()