"""Scan a headerless/truncated ZIP by walking local file header signatures.
Report structure without extracting."""
import struct, sys, re, collections

path = r"C:\Users\shrir\Desktop\astroHack\astrogng\koi_lightcurves(1).zip"
LFH = b"PK\x03\x04"

with open(path, "rb") as f:
    data = f.read()

print(f"file size: {len(data):,}")

pos = 0
n = 0
methods = collections.Counter()
flags_dd = 0
kepids = set()
top = collections.Counter()
truncated = False
first_names = []

while True:
    i = data.find(LFH, pos)
    if i < 0:
        break
    if i + 30 > len(data):
        truncated = True
        break
    (sig, ver, flag, method, mtime, mdate, crc,
     csize, usize, nlen, elen) = struct.unpack("<IHHHHHIIIHH", data[i:i+30])
    name_start = i + 30
    name_end = name_start + nlen
    if name_end > len(data):
        truncated = True
        break
    name = data[name_start:name_end].decode("utf-8", "replace")
    methods[method] += 1
    if flag & 0x8:
        flags_dd += 1
    if n < 5:
        first_names.append((name, method, csize, usize, bool(flag & 0x8)))
    parts = name.split("/")
    if parts:
        top[parts[0]] += 1
    m = re.search(r"kplr(\d+)_lc", name)
    if m:
        kepids.add(m.group(1))
    # advance
    data_start = name_end + elen
    if (flag & 0x8) and csize == 0:
        # data descriptor, unknown size -> jump to next LFH
        pos = data_start
    else:
        pos = data_start + csize
    n += 1

print(f"local file headers found: {n}")
print(f"methods (0=store,8=deflate): {dict(methods)}")
print(f"entries using data descriptor: {flags_dd}")
print(f"distinct kepler target folders: {len(kepids)}")
print(f"top-level dirs: {dict(list(top.items())[:10])}")
print(f"appears truncated mid-entry: {truncated}")
print("first entries (name, method, csize, usize, dd):")
for r in first_names:
    print("  ", r)
