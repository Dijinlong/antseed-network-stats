#!/usr/bin/env python3
"""
antseed network stats
=====================

Flatten `antseed network browse --json` into one row per seller.

Why
---
The raw output is per-peer and deeply nested. The question you actually have is
"where do I sit, and who is cheaper", and that question wants a table, not a
tree.

Usage
-----
    antseed network browse --json --top 500 --sort volume > raw.json
    python stats.py raw.json
    python stats.py raw.json --sort trust
    python stats.py raw.json --min-trust 60
    python stats.py raw.json --json out.json

Input shape (from `antseed network browse --json`)
--------------------------------------------------
    {
      "total": 52,
      "peers": [
        {
          "peerId": "4f29...",
          "displayName": "Some Seller",
          "trust": {"score": 61.2, "history": {...}, "usage": {...},
                    "power": {...}, "identity": {...}, "washFlagged": false},
          "onChainTotalVolumeUsdcMicros": 52876316784,
          "onChainPoolStakeAnts": 27792,
          "providerPricing": {
            "<provider>": {
              "defaults": {"inputUsdPerMillion": 0.35, "outputUsdPerMillion": 1.75},
              "services": {"model-a": {"inputUsdPerMillion": 0.3,
                                       "outputUsdPerMillion": 1.5}}
            }
          }
        }
      ]
    }
"""

import argparse
import json
import sys

USDC = 1_000_000.0  # micros -> USDC


def best_price(peer):
    """Cheapest (input + output) offer this peer advertises.

    Returns (total, model, input, output) or None.
    """
    best = None
    pricing = peer.get("providerPricing") or {}
    if not isinstance(pricing, dict):
        return None
    for block in pricing.values():
        if not isinstance(block, dict):
            continue
        services = block.get("services") or {}
        if not isinstance(services, dict):
            continue
        for model, p in services.items():
            if not isinstance(p, dict):
                continue
            i = p.get("inputUsdPerMillion")
            o = p.get("outputUsdPerMillion")
            if not isinstance(i, (int, float)) or not isinstance(o, (int, float)):
                continue
            total = i + o
            if best is None or total < best[0]:
                best = (total, model, i, o)
    return best


def price_for(peer, model):
    """Cheapest offer for one specific model. Returns (input, output) or None."""
    best = None
    pricing = peer.get("providerPricing") or {}
    if not isinstance(pricing, dict):
        return None
    for block in pricing.values():
        if not isinstance(block, dict):
            continue
        p = (block.get("services") or {}).get(model)
        if not isinstance(p, dict):
            continue
        i = p.get("inputUsdPerMillion")
        o = p.get("outputUsdPerMillion")
        if not isinstance(i, (int, float)) or not isinstance(o, (int, float)):
            continue
        if best is None or (i + o) < (best[0] + best[1]):
            best = (i, o)
    return best


def trust_parts(peer):
    t = peer.get("trust") or {}
    def sc(name):
        v = t.get(name)
        return v.get("score") if isinstance(v, dict) else None
    return {
        "score": t.get("score"),
        "history": sc("history"),
        "usage": sc("usage"),
        "power": sc("power"),
        "identity": sc("identity"),
        "wash": t.get("washFlagged"),
    }


def normalize(peer):
    t = trust_parts(peer)
    vol_micros = peer.get("onChainTotalVolumeUsdcMicros") or 0
    bp = best_price(peer)
    return {
        "peerId": peer.get("peerId") or "",
        "name": peer.get("displayName") or "(unnamed)",
        "trust": t["score"],
        "history": t["history"],
        "usage": t["usage"],
        "power": t["power"],
        "identity": t["identity"],
        "wash": bool(t["wash"]),
        "volume": (vol_micros / USDC) if isinstance(vol_micros, (int, float)) else 0.0,
        "channels": peer.get("onChainChannelCount") or 0,
        "stake": peer.get("onChainPoolStakeAnts") or 0,
        "best_total": bp[0] if bp else None,
        "best_model": bp[1] if bp else "",
        "best_in": bp[2] if bp else None,
        "best_out": bp[3] if bp else None,
    }


def fmt_num(v, nd=4):
    return "-" if v is None else ("%.*f" % (nd, v))


def table(rows, model=None, show_trust_parts=False):
    if model:
        head = "%-30s %8s %8s %8s %10s" % ("卖家", "输入$", "输出$", "合计$", "信任分")
    elif show_trust_parts:
        head = "%-30s %7s %7s %7s %7s %7s %6s" % (
            "卖家", "总分", "成交", "用量", "质押", "身份", "刷单")
    else:
        head = "%-30s %7s %10s %8s %8s %-16s" % (
            "卖家", "信任分", "流水USDC", "质押", "单数", "最便宜模型")
    print(head)
    print("-" * len(head))

    for r in rows:
        if model:
            print("%-30s %8s %8s %8s %10s" % (
                r["name"][:30], fmt_num(r.get("p_in")), fmt_num(r.get("p_out")),
                fmt_num(r.get("p_total")), fmt_num(r["trust"], 1)))
        elif show_trust_parts:
            print("%-30s %7s %7s %7s %7s %7s %6s" % (
                r["name"][:30], fmt_num(r["trust"], 1), fmt_num(r["history"], 0),
                fmt_num(r["usage"], 1), fmt_num(r["power"], 1),
                fmt_num(r["identity"], 1), "是" if r["wash"] else "否"))
        else:
            print("%-30s %7s %10s %8s %8s %-16s" % (
                r["name"][:30], fmt_num(r["trust"], 1), "%.0f" % r["volume"],
                r["stake"], r["channels"], (r["best_model"] or "-")[:16]))


def main():
    ap = argparse.ArgumentParser(description="Summarise antseed network sellers.")
    ap.add_argument("raw", help="output of `antseed network browse --json`")
    ap.add_argument("--sort", default="volume",
                    choices=["volume", "trust", "stake", "channels", "name", "price"])
    ap.add_argument("--min-trust", type=float, default=None,
                    help="only sellers at or above this trust score")
    ap.add_argument("--model", default=None,
                    help="show per-model prices instead of the summary table")
    ap.add_argument("--trust-parts", action="store_true",
                    help="break the trust score into its four components")
    ap.add_argument("--json", dest="json_out", default=None,
                    help="also write the flattened records to this file")
    args = ap.parse_args()

    with open(args.raw, encoding="utf-8") as fh:
        data = json.load(fh)

    peers = data.get("peers") or []
    rows = [normalize(p) for p in peers]

    if args.min_trust is not None:
        rows = [r for r in rows if isinstance(r["trust"], (int, float))
                and r["trust"] >= args.min_trust]

    if args.model:
        for r in rows:
            pr = price_for_by_id(peers, r["peerId"], args.model)
            r["p_in"] = pr[0] if pr else None
            r["p_out"] = pr[1] if pr else None
            r["p_total"] = (pr[0] + pr[1]) if pr else None
        rows = [r for r in rows if r["p_total"] is not None]
        rows.sort(key=lambda r: r["p_total"])
    elif args.sort == "price":
        rows = [r for r in rows if r["best_total"] is not None]
        rows.sort(key=lambda r: r["best_total"])
    elif args.sort == "name":
        rows.sort(key=lambda r: r["name"].lower())
    else:
        rows.sort(key=lambda r: (r[args.sort] if isinstance(r.get(args.sort), (int, float)) else -1),
                  reverse=True)

    print("全网卖家：%d 个（快照取自 %s）"
          % (data.get("total", len(peers)), data.get("onChainStatsRefreshedAt", "?")))
    if args.model:
        print("按模型比价：%s" % args.model)
    print()
    table(rows, model=args.model, show_trust_parts=args.trust_parts)

    if rows and not args.model:
        print()
        active = [r for r in rows if r["channels"] > 0]
        print("有成交的：%d / %d" % (len(active), len(rows)))
        over60 = [r for r in rows if isinstance(r["trust"], (int, float)) and r["trust"] >= 60]
        print("信任分 >= 60（买家默认门槛）：%d 个" % len(over60))

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2, ensure_ascii=False)
        print("\n已写出：%s" % args.json_out)

    return 0


def price_for_by_id(peers, peer_id, model):
    for p in peers:
        if p.get("peerId") == peer_id:
            return price_for(p, model)
    return None


if __name__ == "__main__":
    sys.exit(main())
