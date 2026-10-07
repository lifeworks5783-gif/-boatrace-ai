from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from collections import defaultdict
from pathlib import Path

from evaluate_down_signal import normalize_race_id, parse_actual, payout_value, read_csv, signal_from_rows


VERSION = "fujin_raijin_buff_debuff_search_v1_20261007"
BET = 100

FUJIN_TARGETS = ("rank1", "negative_top3", "top3")
FUJIN_SCHEMES = (
    ("fixed", 2.0),
    ("fixed", 4.0),
    ("fixed", 6.0),
    ("drop_ratio", 0.25),
    ("drop_ratio", 0.50),
    ("drop_ratio", 0.75),
)
LEVEL_PROFILES = {
    "soft": {1: 0.75, 2: 1.00, 3: 1.25},
    "linear": {1: 1.00, 2: 1.50, 3: 2.00},
}
RAIJIN_MULTIPLIERS = (0.25, 0.50, 0.75, 1.00, 1.25)
RAIJIN_RANK_ATTENUATION = {
    "soft": {4: 1.00, 5: 0.80, 6: 0.60},
    "flat": {4: 1.00, 5: 1.00, 6: 1.00},
}


def parse_args():
    p = argparse.ArgumentParser(description="風神デバフ・雷神バフの買い目サンドボックス探索")
    p.add_argument("--date", required=False, help="日次PDCA対象日 YYYYMMDD")
    return p.parse_args()


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def i(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def rate(n, d):
    return round(100.0 * n / d, 2) if d else None


def valid_combinations(first_candidates, second_candidates, third_candidates):
    out = []
    for a, b, c in itertools.product(first_candidates, second_candidates, third_candidates):
        if len({a, b, c}) == 3:
            out.append((a, b, c))
    return list(dict.fromkeys(out))


def combo_strength(combo, score_by_boat):
    a, b, c = combo
    return score_by_boat[a] * 0.50 + score_by_boat[b] * 0.30 + score_by_boat[c] * 0.20


def build_formation(boats):
    if len(boats) < 3:
        return None
    order = [i(x.get("boat")) for x in boats]
    scores = [f(x.get("score")) for x in boats]
    if any(x is None for x in order) or any(x is None for x in scores):
        return None

    sb = {i(x.get("boat")): f(x.get("score")) or 0.0 for x in boats}
    gap12 = scores[0] - scores[1]
    gap23 = scores[1] - scores[2]

    if gap12 < 5.0 and gap23 >= 10.0:
        kind = "1・2着折返し＋3着流し"
        top1, top2 = order[0], order[1]
        tail = order[2:]
        combos = [(top1, top2, c) for c in tail] + [(top2, top1, c) for c in tail]
    elif gap12 >= 10.0 and gap23 >= 10.0:
        kind = "1・2着固定＋3着流し"
        top1, top2 = order[0], order[1]
        tail = order[2:]
        combos = [(top1, top2, c) for c in tail]
    elif gap12 >= 10.0:
        kind = "1着固定＋相手流し"
        top1 = order[0]
        tail = order[1:]
        combos = [(top1, b, c) for b in tail for c in tail if b != c]
        combos.sort(key=lambda x: (-combo_strength(x, sb), x))
        combos = combos[:12]
    elif gap12 >= 5.0:
        kind = "準軸"
        combos = valid_combinations(order[:2], order[:3], order[:4])
        combos.sort(key=lambda x: (-combo_strength(x, sb), x))
        combos = combos[:8]
    else:
        kind = "混戦"
        combos = valid_combinations(order[:2], order[:4], order[:5])
        combos.sort(key=lambda x: (-combo_strength(x, sb), x))
        combos = combos[:12]

    return {
        "type": kind,
        "combinations": combos,
        "points": len(combos),
        "gap12": round(gap12, 3),
        "gap23": round(gap23, 3),
    }


def discover_dates():
    dates = []
    for p in Path("predictions").glob("????/??/??/live/live_predictions_final_????????.csv"):
        d = p.stem.rsplit("_", 1)[-1]
        if len(d) != 8 or not d.isdigit():
            continue
        rp = Path("archive") / d[:4] / d[4:6] / d[6:8] / f"results_{d}_all.csv"
        if rp.is_file():
            dates.append(d)
    return sorted(set(dates))


def load_races(d):
    y, m, day = d[:4], d[4:6], d[6:8]
    lp = Path("predictions") / y / m / day / "live" / f"live_predictions_final_{d}.csv"
    rp = Path("archive") / y / m / day / f"results_{d}_all.csv"
    live = read_csv(lp)
    results = read_csv(rp)

    grouped = defaultdict(list)
    for row in live:
        k = normalize_race_id(row.get("race_id"))
        if k:
            grouped[k].append(row)

    result_map = {}
    for row in results:
        k = normalize_race_id(row.get("race_id") or row.get("レースコード"))
        if k:
            result_map[k] = row

    out = []
    for k, rows in sorted(grouped.items()):
        result = result_map.get(k)
        if result is None:
            continue
        sig = signal_from_rows(rows)
        if sig is None:
            continue
        actual = parse_actual(result)
        if len(actual) != 3:
            continue

        ranked = sig["ranked"]
        base_boats = []
        deltas = {}
        for rank, row in enumerate(ranked, 1):
            boat = i(row.get("boat"))
            score = f(row.get("score"))
            morning = f(row.get("morning_score_reference"))
            if boat is None or score is None or morning is None:
                base_boats = []
                break
            base_boats.append({"boat": boat, "score": score, "rank": rank})
            deltas[boat] = score - morning
        if len(base_boats) != 6:
            continue

        base_form = build_formation(base_boats)
        if not base_form:
            continue

        out.append({
            "date": d,
            "race_id": k,
            "actual": tuple(actual),
            "payout": payout_value(result),
            "base_boats": base_boats,
            "base_form": base_form,
            "deltas": deltas,
            "fujin_level": int(sig.get("down_level") or 0),
            "raijin_level": int(sig.get("raijin_level") or 0),
            "raijin_candidates": sig.get("raijin_candidates") or [],
        })
    return out


def variant_key(v):
    return (
        f"F:{v['fujin_target']}:{v['fujin_mode']}:{v['fujin_strength']}:"
        f"{v['fujin_level_profile']}|R:{v['raijin_multiplier']}:"
        f"{v['raijin_level_profile']}:{v['raijin_rank_attenuation']}"
    )


def adjusted_formation(race, v):
    boats = [dict(x) for x in race["base_boats"]]
    score = {x["boat"]: float(x["score"]) for x in boats}
    deltas = race["deltas"]

    fl = race["fujin_level"]
    if fl > 0:
        profile = LEVEL_PROFILES[v["fujin_level_profile"]]
        lm = profile[fl]
        top3 = [x["boat"] for x in race["base_boats"][:3]]
        if v["fujin_target"] == "rank1":
            targets = top3[:1]
        elif v["fujin_target"] == "negative_top3":
            targets = [b for b in top3 if deltas.get(b, 0.0) < 0]
        else:
            targets = top3

        for b in targets:
            if v["fujin_mode"] == "fixed":
                penalty = v["fujin_strength"] * lm
            else:
                penalty = max(0.0, -deltas.get(b, 0.0)) * v["fujin_strength"] * lm
            score[b] -= penalty

    rl = race["raijin_level"]
    if rl > 0:
        profile = LEVEL_PROFILES[v["raijin_level_profile"]]
        lm = profile[rl]
        att = RAIJIN_RANK_ATTENUATION[v["raijin_rank_attenuation"]]
        for c in race["raijin_candidates"]:
            b = i(c.get("boat"))
            rise = f(c.get("rise"))
            rank = i(c.get("rank"))
            if b is None or rise is None or rank is None:
                continue
            score[b] += rise * v["raijin_multiplier"] * lm * att.get(rank, 1.0)

    adjusted = [{"boat": b, "score": s} for b, s in score.items()]
    adjusted.sort(key=lambda x: (-x["score"], x["boat"]))
    for rank, row in enumerate(adjusted, 1):
        row["rank"] = rank
    return build_formation(adjusted), adjusted


def empty_metrics():
    return {
        "races": 0, "signal_races": 0, "hits": 0, "points": 0,
        "investment": 0, "return": 0, "manshu_hits": 0,
        "rescued": 0, "lost": 0, "raijin_entry_gain": 0,
    }


def finalize(m):
    n = m["races"]
    inv = m["investment"]
    return {
        **m,
        "hit_rate_pct": rate(m["hits"], n),
        "avg_points": round(m["points"] / n, 3) if n else None,
        "roi_pct": round(100.0 * m["return"] / inv, 2) if inv else None,
        "net_rescues": m["rescued"] - m["lost"],
    }


def evaluate(races, v=None):
    m = empty_metrics()
    for race in races:
        base = race["base_form"]
        base_combos = set(base["combinations"])
        if v is None:
            form = base
        else:
            form, _ = adjusted_formation(race, v)
            if not form:
                continue
        combos = set(form["combinations"])
        actual = race["actual"]
        payout = int(race["payout"] or 0)
        bh = actual in base_combos
        h = actual in combos
        sig = race["fujin_level"] > 0 or race["raijin_level"] > 0

        m["races"] += 1
        m["signal_races"] += int(sig)
        m["points"] += len(combos)
        m["investment"] += BET * len(combos)
        if h:
            m["hits"] += 1
            m["return"] += payout
            m["manshu_hits"] += int(payout >= 10000)
        if v is not None:
            m["rescued"] += int(h and not bh)
            m["lost"] += int(bh and not h)

            if race["raijin_level"] > 0:
                candidates = {i(x.get("boat")) for x in race["raijin_candidates"]}
                candidates.discard(None)
                before_present = any(any(b in c for c in base_combos) for b in candidates)
                after_present = any(any(b in c for c in combos) for b in candidates)
                m["raijin_entry_gain"] += int(after_present and not before_present)
    return finalize(m)


def presence_group(race):
    f_on = race["fujin_level"] > 0
    r_on = race["raijin_level"] > 0
    if f_on and r_on:
        return "both"
    if f_on:
        return "fujin_only"
    if r_on:
        return "raijin_only"
    return "neither"


def grouped_metrics(races, v):
    groups = {}
    for name in ("neither", "fujin_only", "raijin_only", "both"):
        rs = [x for x in races if presence_group(x) == name]
        groups[name] = {
            "baseline": evaluate(rs, None),
            "adjusted": evaluate(rs, v),
        }
    combos = {}
    for fl in range(4):
        for rl in range(4):
            rs = [x for x in races if x["fujin_level"] == fl and x["raijin_level"] == rl]
            combos[f"F{fl}_R{rl}"] = {
                "baseline": evaluate(rs, None),
                "adjusted": evaluate(rs, v),
            }
    return {"presence": groups, "levels": combos}


def candidate_variants():
    for ft, (fm, fs), fp, rm, rp, ra in itertools.product(
        FUJIN_TARGETS,
        FUJIN_SCHEMES,
        LEVEL_PROFILES,
        RAIJIN_MULTIPLIERS,
        LEVEL_PROFILES,
        RAIJIN_RANK_ATTENUATION,
    ):
        yield {
            "fujin_target": ft,
            "fujin_mode": fm,
            "fujin_strength": fs,
            "fujin_level_profile": fp,
            "raijin_multiplier": rm,
            "raijin_level_profile": rp,
            "raijin_rank_attenuation": ra,
        }


def rank_key(row):
    a = row["train"]
    return (
        -(a["hits"]),
        -(a["net_rescues"]),
        a["lost"],
        a["avg_points"] if a["avg_points"] is not None else 999,
        -(a["roi_pct"] if a["roi_pct"] is not None else -999),
    )


def main():
    args = parse_args()
    dates = discover_dates()
    if not dates:
        raise RuntimeError("保存済み予測＋結果がありません")

    races_by_date = {d: load_races(d) for d in dates}
    analyzable = [d for d in dates if races_by_date[d]]
    if len(analyzable) < 3:
        raise RuntimeError("時系列分割に必要な日数が不足しています")

    latest = args.date if args.date in analyzable else analyzable[-1]
    older = [d for d in analyzable if d != latest]
    validation_dates = older[-1:] if len(older) >= 2 else []
    train_dates = [d for d in older if d not in validation_dates]
    if not train_dates:
        train_dates = older[:-1] or older
        validation_dates = [d for d in older if d not in train_dates]

    train_races = [r for d in train_dates for r in races_by_date[d]]
    validation_races = [r for d in validation_dates for r in races_by_date[d]]
    latest_races = races_by_date[latest]
    all_races = [r for d in analyzable for r in races_by_date[d]]

    baseline = {
        "train": evaluate(train_races, None),
        "validation": evaluate(validation_races, None),
        "latest": evaluate(latest_races, None),
        "all": evaluate(all_races, None),
    }

    candidates = []
    for v in candidate_variants():
        row = {
            "key": variant_key(v),
            "params": v,
            "train": evaluate(train_races, v),
        }
        candidates.append(row)

    candidates.sort(key=rank_key)
    top = candidates[:40]
    for row in top:
        v = row["params"]
        row["validation"] = evaluate(validation_races, v)
        row["latest"] = evaluate(latest_races, v)
        row["all"] = evaluate(all_races, v)
        row["all_breakdown"] = grouped_metrics(all_races, v)

    # Validation ranking is reported separately; selection itself remains training-only.
    top_by_validation = sorted(
        top,
        key=lambda x: (
            -(x["validation"]["hits"]),
            -(x["validation"]["net_rescues"]),
            x["validation"]["lost"],
            x["validation"]["avg_points"] if x["validation"]["avg_points"] is not None else 999,
            -(x["validation"]["roi_pct"] if x["validation"]["roi_pct"] is not None else -999),
        ),
    )

    out = {
        "version": VERSION,
        "production_changed": False,
        "prediction_effect": False,
        "formation_effect": False,
        "purpose": "風神デバフ・雷神バフを通常スコアへ仮適用し、現行formation_gap_flow_v2相当の買い目を再生成して検証",
        "guardrails": {
            "uses_saved_pre_result_scores": True,
            "result_used_only_for_settlement": True,
            "production_logic_unchanged": True,
            "candidate_selection_uses_training_only": True,
            "note": "シグナル閾値自体は既に最近データを見て設計されているため、validation/latestは完全な独立外部検証ではない",
        },
        "dates": {
            "analyzable": analyzable,
            "train": train_dates,
            "validation": validation_dates,
            "latest": latest,
        },
        "search_space": len(candidates),
        "baseline": baseline,
        "parameter_space": {
            "fujin_targets": list(FUJIN_TARGETS),
            "fujin_schemes": [{"mode": m, "strength": s} for m, s in FUJIN_SCHEMES],
            "level_profiles": LEVEL_PROFILES,
            "raijin_multipliers": list(RAIJIN_MULTIPLIERS),
            "raijin_rank_attenuation": RAIJIN_RANK_ATTENUATION,
        },
        "top40_selected_on_training": top,
        "top10_by_validation_among_training_top40": top_by_validation[:10],
    }

    out_dir = Path("evaluations") / "fujin_raijin" / "buff_debuff"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_fields = [
        "rank", "key",
        "fujin_target", "fujin_mode", "fujin_strength", "fujin_level_profile",
        "raijin_multiplier", "raijin_level_profile", "raijin_rank_attenuation",
        "train_hits", "train_hit_rate_pct", "train_rescued", "train_lost", "train_net_rescues", "train_roi_pct", "train_avg_points",
        "validation_hits", "validation_hit_rate_pct", "validation_rescued", "validation_lost", "validation_net_rescues", "validation_roi_pct", "validation_avg_points",
        "latest_hits", "latest_hit_rate_pct", "latest_rescued", "latest_lost", "latest_net_rescues", "latest_roi_pct", "latest_avg_points",
        "all_hits", "all_hit_rate_pct", "all_rescued", "all_lost", "all_net_rescues", "all_roi_pct", "all_avg_points", "all_manshu_hits",
    ]
    with (out_dir / "top40.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=summary_fields)
        w.writeheader()
        for rank, row in enumerate(top, 1):
            p = row["params"]
            z = {
                "rank": rank, "key": row["key"],
                "fujin_target": p["fujin_target"],
                "fujin_mode": p["fujin_mode"],
                "fujin_strength": p["fujin_strength"],
                "fujin_level_profile": p["fujin_level_profile"],
                "raijin_multiplier": p["raijin_multiplier"],
                "raijin_level_profile": p["raijin_level_profile"],
                "raijin_rank_attenuation": p["raijin_rank_attenuation"],
            }
            for split in ("train", "validation", "latest", "all"):
                for field in ("hits", "hit_rate_pct", "rescued", "lost", "net_rescues", "roi_pct", "avg_points"):
                    z[f"{split}_{field}"] = row[split][field]
            z["all_manshu_hits"] = row["all"]["manshu_hits"]
            w.writerow(z)

    print(json.dumps({
        "version": VERSION,
        "production_changed": False,
        "search_space": len(candidates),
        "dates": out["dates"],
        "baseline": baseline,
        "training_best": {
            "key": top[0]["key"],
            "params": top[0]["params"],
            "train": top[0]["train"],
            "validation": top[0]["validation"],
            "latest": top[0]["latest"],
            "all": top[0]["all"],
        } if top else None,
        "output": str(out_dir / "latest.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
