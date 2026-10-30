#!/usr/bin/env bash
# List pod GPU availability (SECURE + COMMUNITY). Requires RUNPOD_API_KEY.
set -euo pipefail

: "${RUNPOD_API_KEY:?export RUNPOD_API_KEY first}"

python3 - "$RUNPOD_API_KEY" <<'PY'
import json, os, sys, urllib.request

key = sys.argv[1]
order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NONE": 3}

for cloud in ("SECURE", "COMMUNITY"):
    print(f"\n=== {cloud} ===")
    url = (
        "https://api.runpod.io/v2/catalog/gpus"
        f"?include=AVAILABILITY&product=POD&cloud={cloud}&count=1"
    )
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    items = data.get("gpus") or []
    rows = []
    for g in items:
        av = g.get("availability") or "NONE"
        # Do not put dicts in the sort key — ties would TypeError on dict < dict.
        rows.append((order.get(av, 9), -(g.get("memory") or 0), g.get("id") or "", g))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    for _, __, ___, g in rows:
        av = g.get("availability") or "NONE"
        if av == "NONE":
            continue
        price = g.get("price") or {}
        rate = price.get("community") if cloud == "COMMUNITY" else price.get("secure")
        dcs = [
            f"{dc.get('id')}={dc.get('availability')}"
            for dc in (g.get("dataCenters") or [])
            if dc.get("availability") not in (None, "NONE")
        ][:6]
        print(f"{av:6}  {g.get('id'):42}  ${rate}/hr  {', '.join(dcs)}")
PY
