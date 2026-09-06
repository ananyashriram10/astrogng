"""
Recover koi_lightcurves(1).zip (central directory missing/unreadable) by walking
local file headers. Most entries are deflate + streaming data descriptor, so we
decompress each stream to find its true length.

Extracts/merges into koi_lightcurves/mastDownload/Kepler/ next to our own download.
Existing files are kept (not overwritten).
"""
import struct, zlib, os, re, sys, time

ZIP = r"C:\Users\shrir\Desktop\astroHack\astrogng\koi_lightcurves(1).zip"
DEST_ROOT = r"C:\Users\shrir\Desktop\astroHack"   # zip paths start with koi_lightcurves/...
LFH = b"PK\x03\x04"
CEN = b"PK\x01\x02"

with open(ZIP, "rb") as f:
    data = f.read()
size = len(data)
mv = memoryview(data)
print(f"zip size: {size:,} bytes")

pos = 0
n_files = n_dirs = n_skipped = n_written = 0
bytes_written = 0
errors = []
new_kepids = set()
start = time.time()

while True:
    i = data.find(LFH, pos)
    if i < 0 or i + 30 > size:
        break
    (sig, ver, flag, method, mtime, mdate, crc,
     csize, usize, nlen, elen) = struct.unpack("<IHHHHHIIIHH", data[i:i+30])
    name_start = i + 30
    name_end = name_start + nlen
    if name_end + elen > size:
        errors.append(f"truncated header at {i}")
        break
    name = data[name_start:name_end].decode("utf-8", "replace")
    data_start = name_end + elen

    if name.endswith("/"):
        n_dirs += 1
        os.makedirs(os.path.join(DEST_ROOT, name.replace("/", os.sep)), exist_ok=True)
        pos = data_start
        continue

    # ---- get file content ----
    content = None
    if method == 0:
        if flag & 0x8:
            # stored + dd: length unknown from header; find next PK signature
            j = data.find(b"PK", data_start)
            content = data[data_start:j]
            pos = j
        else:
            content = data[data_start:data_start + csize]
            pos = data_start + csize
    elif method == 8:
        d = zlib.decompressobj(-15)
        CHUNK = 1 << 20
        parts = []
        p = data_start
        try:
            while not d.eof and p < size:
                parts.append(d.decompress(mv[p:p+CHUNK]))
                p += CHUNK
            parts.append(d.flush())
        except Exception as e:
            errors.append(f"{name}: inflate error {e}")
            pos = data_start + 1
            continue
        content = b"".join(parts)
        # p overshot in CHUNK steps; back off by leftover unused bytes
        p = p - len(d.unused_data) if d.eof else size
        # optional data descriptor: [PK\x07\x08] crc(4) csize(4) usize(4).
        # Snap to the next PK record rather than guessing its length.
        dd = data.find(b"PK\x07\x08", p)
        if dd != -1 and dd <= p + 4:
            pos = dd + 16
        else:
            pos = p
    else:
        errors.append(f"{name}: unknown method {method}")
        pos = data_start + 1
        continue

    if usize and len(content) != usize:
        errors.append(f"{name}: size mismatch got {len(content)} want {usize}")
        # still write what we have

    dest = os.path.join(DEST_ROOT, name.replace("/", os.sep))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    n_files += 1
    m = re.search(r"kplr(\d+)_lc", name)
    if m:
        new_kepids.add(int(m.group(1)))
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        n_skipped += 1
    else:
        with open(dest, "wb") as out_f:
            out_f.write(content)
        n_written += 1
        bytes_written += len(content)

    if n_files % 500 == 0:
        print(f"  {n_files} files ... written={n_written} skipped={n_skipped} "
              f"errs={len(errors)} ({bytes_written/1e6:.0f} MB) [{time.time()-start:.0f}s]")

print(f"\nDONE in {time.time()-start:.0f}s")
print(f"dirs: {n_dirs}, file entries: {n_files}")
print(f"written: {n_written}, skipped (already present): {n_skipped}")
print(f"bytes written: {bytes_written:,}")
print(f"distinct kepids in zip: {len(new_kepids)}")
print(f"errors: {len(errors)}")
for e in errors[:20]:
    print("  ", e)
