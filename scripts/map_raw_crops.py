"""Map raw/ files by embedded DJI id to find missing Photoshop crops."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

raw = Path("raw")
files = list(raw.rglob("*.jpg")) + list(raw.rglob("*.JPG")) + list(raw.rglob("*.jpeg"))
# dedupe by resolve
seen = set()
uniq = []
for p in files:
    r = p.resolve()
    if r in seen:
        continue
    seen.add(r)
    uniq.append(p)

by_dji: dict[str, list] = defaultdict(list)
no_dji = []
for p in uniq:
    rel = p.relative_to(raw).as_posix()
    name = p.name
    m = re.search(r"(DJI_\d+_[A-Za-z0-9]+)", name, re.I)
    dji = m.group(1).upper() if m else None
    if name.lower().startswith("gbh_fly"):
        kind = "gbh_fly"
    elif name.upper().startswith("DJI_"):
        kind = "dji"
    else:
        kind = "other"
    loc = "exp" if rel.startswith("exp/") else ("root" if "/" not in rel else f"sub:{rel.split('/')[0]}")
    row = {"rel": rel, "name": name, "dji": dji, "kind": kind, "loc": loc}
    if dji:
        by_dji[dji].append(row)
    else:
        no_dji.append(row)

print(f"total files: {len(uniq)}")
print(f"unique DJI ids: {len(by_dji)}")
print(f"no DJI id in name: {len(no_dji)}")
for it in no_dji:
    print(f"  {it['rel']}")

mult = Counter(len(v) for v in by_dji.values())
print("\ncopies per DJI id:", dict(sorted(mult.items())))


def label(x):
    return f"{x['kind']}@{x['loc']}"


singles, pairs, triples = [], [], []
missing_crop = []  # DJI at root, no gbh_fly anywhere
missing_orig = []  # gbh_fly, no DJI at root
for dji, lst in sorted(by_dji.items()):
    n = len(lst)
    if n == 1:
        singles.append((dji, lst))
    elif n == 2:
        pairs.append((dji, lst))
    else:
        triples.append((dji, lst))
    has_fly = any(x["kind"] == "gbh_fly" for x in lst)
    has_dji_root = any(x["kind"] == "dji" and x["loc"] == "root" for x in lst)
    if has_dji_root and not has_fly:
        missing_crop.append((dji, [x["rel"] for x in lst]))
    if has_fly and not has_dji_root:
        missing_orig.append((dji, [x["rel"] for x in lst]))

print(f"\n=== 1 copy only: {len(singles)} ===")
for dji, lst in singles:
    print(f"  {dji}  <-  {lst[0]['rel']}")

print(f"\n=== 2 copies: {len(pairs)} — patterns ===")
pp = Counter(tuple(sorted(label(x) for x in lst)) for _, lst in pairs)
for k, v in pp.most_common():
    print(f"  {v}x  {k}")

print(f"\n=== 3+ copies: {len(triples)} — patterns ===")
tp = Counter(tuple(sorted(label(x) for x in lst)) for _, lst in triples)
for k, v in tp.most_common():
    print(f"  {v}x  {k}")

print(f"\n=== DJI original at raw/, NO gbh_fly crop: {len(missing_crop)} ===")
for dji, rels in missing_crop:
    print(f"  {dji}")
    for r in rels:
        print(f"      {r}")

print(f"\n=== gbh_fly exists, NO DJI at raw/ root: {len(missing_orig)} ===")
for dji, rels in missing_orig:
    print(f"  {dji}")
    for r in rels:
        print(f"      {r}")

# gbh_fly sequence gaps
fly_nums = []
for p in uniq:
    m = re.match(r"gbh_fly_(\d+)_", p.name, re.I)
    if m and not str(p.relative_to(raw)).startswith("exp"):
        fly_nums.append(int(m.group(1)))
fly_nums = sorted(set(fly_nums))
if fly_nums:
    print(f"\ngbh_fly index range at root: {fly_nums[0]} .. {fly_nums[-1]} ({len(fly_nums)} files)")
    missing_idx = [i for i in range(fly_nums[0], fly_nums[-1] + 1) if i not in fly_nums]
    print(f"missing gbh_fly_NNNN indices: {missing_idx if missing_idx else 'none'}")
