from __future__ import annotations

import argparse
import csv
import itertools
import json
from collections import defaultdict
from pathlib import Path

from evaluate_fujin_raijin_buff_debuff_search import (
    BET,
    adjusted_formation,
    combo_strength,
    evaluate,
    load_races,
)


VERSION = "fujin_raijin_strength_points_search_v3_20261007"
POINT_CHOICES = tuple(range(6, 25, 2))  # 6,8,10,...,24
TOP_BUFF_VARIANTS = 20


def parse_args():
    p = argparse.ArgumentParser(
        description="風神+雷神の合算強度と買い目6-24点の組み合わせ探索"
    )
    p.add_argument("--date", required=False, help="最新評価日 YYYYMMDD")
    return p.parse_args()


def all120_ranked(adjusted_rows):
    boats = [int(x["boat"]) for x in adjusted_rows]
    score_by_boat = {int(x["boat"]): float(x["score"]) for x in adjusted_rows}
    combos = []
    for a, b, c in itertools.permutations(boats, 3):
        combo = (a, b, c)
        combos.append((combo_strength(combo, score_by_boat), combo))
    combos.sort(key=lambda x: (-x[0], x[1]))
    return [combo for _, combo in combos]


def strength(race):
    # 合算強度: 風神Lv + 雷神Lv = 0..6
    return int(race["fujin_level"]) + int(race["raijin_level"])


def monotonic_policies():
    # 強度0（風神・雷神とも未発動）は買わない=0点。
    # 強度1..6は6-24点の2点刻みで単調非減少。
    # 10種類から重複あり6個選択 = 5005通り。
    for vals in itertools.combinations_with_replacement(POINT_CHOICES, 6):
        yield (0,) + vals


def policy_key(p):
    return "-".join(str(x) for x in p)


def precompute_records(races, params=None):
    records = []
    for race in races:
        if params is None:
            adjusted = [dict(x) for x in race["base_boats"]]
        else:
            _, adjusted = adjusted_formation(race, params)
        ranked = all120_ranked(adjusted)
        try:
            actual_rank = ranked.index(race["actual"]) + 1
        except ValueError:
            continue
        base_hit = race["actual"] in set(race["base_form"]["combinations"])
        records.append({
            "strength": strength(race),
            "actual_rank": actual_rank,
            "payout": int(race["payout"] or 0),
            "base_hit": bool(base_hit),
            "base_points": int(race["base_form"]["points"]),
        })
    return records


def build_lookup(records):
    lookup = {}
    for s in range(7):
        rs = [x for x in records if x["strength"] == s]
        point_candidates = (0,) if s == 0 else POINT_CHOICES
        for n in point_candidates:
            hits = [x for x in rs if n > 0 and x["actual_rank"] <= n]
            lookup[(s, n)] = {
                "races": len(rs),
                "hits": len(hits),
                "return": sum(x["payout"] for x in hits),
                "manshu_hits": sum(1 for x in hits if x["payout"] >= 10000),
                "rescued_vs_current": sum(
                    1 for x in hits if not x["base_hit"]
                ),
                "lost_vs_current": sum(
                    1 for x in rs if x["base_hit"] and x["actual_rank"] > n
                ),
                "points": n * len(rs),
            }
    return lookup


def metrics_from_policy(lookup, policy):
    total = {
        "races": 0,
        "hits": 0,
        "return": 0,
        "manshu_hits": 0,
        "rescued_vs_current": 0,
        "lost_vs_current": 0,
        "points": 0,
    }
    by_strength = {}
    for s in range(7):
        n = policy[s]
        m = dict(lookup[(s, n)])
        m["points_per_race"] = n
        by_strength[str(s)] = m
        for k in total:
            total[k] += m[k]

    races = total["races"]
    investment = total["points"] * BET
    total["investment"] = investment
    total["hit_rate_pct"] = round(100 * total["hits"] / races, 2) if races else None
    total["avg_points"] = round(total["points"] / races, 2) if races else None
    total["roi_pct"] = round(100 * total["return"] / investment, 2) if investment else None
    total["net_rescues_vs_current"] = total["rescued_vs_current"] - total["lost_vs_current"]
    return total, by_strength


def current_baseline(races):
    m = evaluate(races, None)
    return {
        "races": m["races"],
        "hits": m["hits"],
        "hit_rate_pct": m["hit_rate_pct"],
        "avg_points": m["avg_points"],
        "investment": m["investment"],
        "return": m["return"],
        "roi_pct": m["roi_pct"],
        "manshu_hits": m["manshu_hits"],
    }


def add_delta(adjusted, no_buff):
    return {
        **adjusted,
        "vs_same_points_no_buff": {
            "hit_delta": adjusted["hits"] - no_buff["hits"],
            "hit_rate_delta_pt": (
                round(adjusted["hit_rate_pct"] - no_buff["hit_rate_pct"], 2)
                if adjusted["hit_rate_pct"] is not None and no_buff["hit_rate_pct"] is not None
                else None
            ),
            "return_delta": adjusted["return"] - no_buff["return"],
            "roi_delta_pt": (
                round(adjusted["roi_pct"] - no_buff["roi_pct"], 2)
                if adjusted["roi_pct"] is not None and no_buff["roi_pct"] is not None
                else None
            ),
            "manshu_hit_delta": adjusted["manshu_hits"] - no_buff["manshu_hits"],
        },
    }


def pareto(rows):
    # 最大化: hits, ROI / 最小化: avg_points
    frontier = []
    for x in rows:
        xm = x["train"]
        dominated = False
        for y in rows:
            if x is y:
                continue
            ym = y["train"]
            if (
                ym["hits"] >= xm["hits"]
                and (ym["roi_pct"] or -999) >= (xm["roi_pct"] or -999)
                and (ym["avg_points"] or 999) <= (xm["avg_points"] or 999)
                and (
                    ym["hits"] > xm["hits"]
                    or (ym["roi_pct"] or -999) > (xm["roi_pct"] or -999)
                    or (ym["avg_points"] or 999) < (xm["avg_points"] or 999)
                )
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(x)
    frontier.sort(
        key=lambda x: (
            -x["train"]["hits"],
            -(x["train"]["roi_pct"] or -999),
            x["train"]["avg_points"] or 999,
        )
    )
    return frontier


def main():
    args = parse_args()
    source = Path("evaluations/fujin_raijin/buff_debuff/latest.json")
    if not source.is_file():
        raise RuntimeError("先に風神雷神バフ・デバフ探索を実行してください")

    buff_data = json.loads(source.read_text(encoding="utf-8"))
    top = buff_data.get("top40_selected_on_training") or []
    if not top:
        raise RuntimeError("バフ・デバフ候補がありません")

    dates = buff_data["dates"]
    latest = args.date if args.date in dates["analyzable"] else dates["latest"]
    train_dates = dates["train"]
    validation_dates = dates["validation"]

    races_by_date = {d: load_races(d) for d in dates["analyzable"]}
    splits = {
        "train": [r for d in train_dates for r in races_by_date[d]],
        "validation": [r for d in validation_dates for r in races_by_date[d]],
        "latest": races_by_date[latest],
        "all": [r for d in dates["analyzable"] for r in races_by_date[d]],
    }

    policies = list(monotonic_policies())
    no_buff_lookup = {
        name: build_lookup(precompute_records(rs, None))
        for name, rs in splits.items()
    }
    current = {name: current_baseline(rs) for name, rs in splits.items()}

    candidates = []
    for buff_rank, buff_row in enumerate(top[:TOP_BUFF_VARIANTS], 1):
        params = buff_row["params"]
        adj_lookup = {
            name: build_lookup(precompute_records(rs, params))
            for name, rs in splits.items()
        }

        for policy in policies:
            item = {
                "buff_rank": buff_rank,
                "buff_key": buff_row["key"],
                "buff_params": params,
                "point_policy": {
                    "strength_0": policy[0],
                    "strength_1": policy[1],
                    "strength_2": policy[2],
                    "strength_3": policy[3],
                    "strength_4": policy[4],
                    "strength_5": policy[5],
                    "strength_6": policy[6],
                },
                "policy_key": policy_key(policy),
            }
            for name in ("train", "validation", "latest", "all"):
                adj, by_strength = metrics_from_policy(adj_lookup[name], policy)
                nob, _ = metrics_from_policy(no_buff_lookup[name], policy)
                item[name] = add_delta(adj, nob)
                if name == "all":
                    item["all_by_strength"] = by_strength
            candidates.append(item)

    # 目的を一つに固定すると24点偏重になるため、用途別トップを保存。
    max_hit = sorted(
        candidates,
        key=lambda x: (
            -x["train"]["hits"],
            x["train"]["avg_points"],
            -(x["train"]["roi_pct"] or -999),
        ),
    )[:30]
    max_roi = sorted(
        candidates,
        key=lambda x: (
            -(x["train"]["roi_pct"] or -999),
            -x["train"]["hits"],
            x["train"]["avg_points"],
        ),
    )[:30]
    max_buff_gain = sorted(
        candidates,
        key=lambda x: (
            -x["train"]["vs_same_points_no_buff"]["hit_delta"],
            -x["train"]["net_rescues_vs_current"],
            x["train"]["avg_points"],
            -(x["train"]["roi_pct"] or -999),
        ),
    )[:30]
    pf = pareto(candidates)

    # 訓練で候補化したものだけを後段データで比較する。
    candidate_ids = []
    for group in (max_hit, max_roi, max_buff_gain, pf[:100]):
        for x in group:
            key = (x["buff_key"], x["policy_key"])
            if key not in candidate_ids:
                candidate_ids.append(key)
    candidate_set = set(candidate_ids)
    short = [x for x in candidates if (x["buff_key"], x["policy_key"]) in candidate_set]

    validation_ranked = sorted(
        short,
        key=lambda x: (
            -x["validation"]["hits"],
            -(x["validation"]["roi_pct"] or -999),
            x["validation"]["avg_points"],
            -x["validation"]["vs_same_points_no_buff"]["hit_delta"],
        ),
    )

    out = {
        "version": VERSION,
        "production_changed": False,
        "prediction_effect": False,
        "formation_effect": False,
        "method": {
            "combined_strength": "風神Lv + 雷神Lv (0-6)",
            "point_range": [0, 24],
            "point_step": 2,
            "strength0_fixed_points": 0,
            "monotonic_points": True,
            "combination_ranking": "補正後艇スコアで全120通りを50/30/20加重し上位N点",
            "note": "風神・雷神とも未発動は0点で見送り。発動レースのみ6-24点で全120通り上位N点を検証する。現行formation_gap_flow_v2は本番比較基準として保持する",
        },
        "search_space": {
            "buff_variants": min(TOP_BUFF_VARIANTS, len(top)),
            "point_policies": len(policies),
            "total_combinations": min(TOP_BUFF_VARIANTS, len(top)) * len(policies),
        },
        "dates": {
            **dates,
            "latest": latest,
        },
        "current_production_baseline": current,
        "top30_training_max_hit": max_hit,
        "top30_training_max_roi": max_roi,
        "top30_training_max_buff_gain": max_buff_gain,
        "training_pareto_frontier": pf[:200],
        "validation_ranking_of_training_shortlist": validation_ranked[:50],
    }

    out_dir = Path("evaluations/fujin_raijin/strength_points")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    fields = [
        "validation_rank", "buff_rank", "buff_key", "policy_key",
        "s0", "s1", "s2", "s3", "s4", "s5", "s6",
        "train_hits", "train_hit_rate_pct", "train_avg_points", "train_roi_pct",
        "train_buff_hit_delta", "train_manshu_hits",
        "validation_hits", "validation_hit_rate_pct", "validation_avg_points", "validation_roi_pct",
        "validation_buff_hit_delta", "validation_manshu_hits",
        "latest_hits", "latest_hit_rate_pct", "latest_avg_points", "latest_roi_pct",
        "latest_buff_hit_delta", "latest_manshu_hits",
        "all_hits", "all_hit_rate_pct", "all_avg_points", "all_roi_pct",
        "all_buff_hit_delta", "all_manshu_hits",
    ]
    with (out_dir / "validation_top50.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for rank, x in enumerate(validation_ranked[:50], 1):
            pp = x["point_policy"]
            row = {
                "validation_rank": rank,
                "buff_rank": x["buff_rank"],
                "buff_key": x["buff_key"],
                "policy_key": x["policy_key"],
                **{f"s{s}": pp[f"strength_{s}"] for s in range(7)},
            }
            for name in ("train", "validation", "latest", "all"):
                m = x[name]
                row[f"{name}_hits"] = m["hits"]
                row[f"{name}_hit_rate_pct"] = m["hit_rate_pct"]
                row[f"{name}_avg_points"] = m["avg_points"]
                row[f"{name}_roi_pct"] = m["roi_pct"]
                row[f"{name}_buff_hit_delta"] = m["vs_same_points_no_buff"]["hit_delta"]
                row[f"{name}_manshu_hits"] = m["manshu_hits"]
            w.writerow(row)

    print(json.dumps({
        "version": VERSION,
        "production_changed": False,
        "search_space": out["search_space"],
        "current_production_baseline": current,
        "best_validation_from_training_shortlist": validation_ranked[0] if validation_ranked else None,
        "output": str(out_dir / "latest.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
