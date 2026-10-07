# 直前情報5項目 個別答え合わせ

対象日：2026/10/07

## 取得カバレッジ

- exhibition_time: 863
- exhibition_st: 863
- exhibition_f: 864
- exhibition_course: 863
- course_changed: 863
- wind_speed: 864
- wind_direction: 846
- wave_height: 864

## 個別要素分析

```json
{
  "exhibition_time": {
    "available": true,
    "races": 144,
    "best_win_rate_pct": 32.6,
    "best_top3_rate_pct": 68.1,
    "worst_win_rate_pct": 4.9,
    "mean_within_race_spearman": 0.2357
  },
  "exhibition_st": {
    "available": true,
    "races": 103,
    "best_win_rate_pct": 22.3,
    "best_top3_rate_pct": 63.1,
    "worst_win_rate_pct": 13.6,
    "mean_within_race_spearman": 0.0755
  },
  "exhibition_f": {
    "available": true,
    "boats": 864,
    "flagged_boats": 235,
    "flagged_win_rate_pct": 15.3,
    "flagged_top3_rate_pct": 49.4,
    "unflagged_win_rate_pct": 17.2,
    "unflagged_top3_rate_pct": 50.2
  },
  "course_changed": {
    "available": true,
    "boats": 863,
    "flagged_boats": 53,
    "flagged_win_rate_pct": 11.3,
    "flagged_top3_rate_pct": 47.2,
    "unflagged_win_rate_pct": 17.0,
    "unflagged_top3_rate_pct": 50.2
  }
}
```

## 風速別

```json
[
  {
    "bucket": "0-2m",
    "races": 64,
    "boat1_win_rate_pct": 65.6
  },
  {
    "bucket": "3-4m",
    "races": 49,
    "boat1_win_rate_pct": 44.9
  },
  {
    "bucket": "5m以上",
    "races": 31,
    "boat1_win_rate_pct": 41.9
  }
]
```

## 展示タイム・ST・F 重み探索

> これは候補探索です。1日だけの結果で本番配点は自動変更しません。

```json
{
  "available": true,
  "available_factors": [
    "exhibition_time",
    "exhibition_st",
    "exhibition_f"
  ],
  "races": 144,
  "baseline_top1_accuracy_pct": 50.0,
  "best_candidates": [
    {
      "exhibition_time_weight": 12,
      "exhibition_st_weight": 0,
      "f_penalty": 0,
      "top1_accuracy_pct": 52.8,
      "improvement_vs_baseline_pt": 2.8
    },
    {
      "exhibition_time_weight": 10,
      "exhibition_st_weight": 0,
      "f_penalty": 0,
      "top1_accuracy_pct": 52.1,
      "improvement_vs_baseline_pt": 2.1
    },
    {
      "exhibition_time_weight": 10,
      "exhibition_st_weight": 0,
      "f_penalty": 2,
      "top1_accuracy_pct": 52.1,
      "improvement_vs_baseline_pt": 2.1
    },
    {
      "exhibition_time_weight": 10,
      "exhibition_st_weight": 4,
      "f_penalty": 0,
      "top1_accuracy_pct": 52.1,
      "improvement_vs_baseline_pt": 2.1
    },
    {
      "exhibition_time_weight": 12,
      "exhibition_st_weight": 2,
      "f_penalty": 0,
      "top1_accuracy_pct": 52.1,
      "improvement_vs_baseline_pt": 2.1
    },
    {
      "exhibition_time_weight": 12,
      "exhibition_st_weight": 2,
      "f_penalty": 2,
      "top1_accuracy_pct": 52.1,
      "improvement_vs_baseline_pt": 2.1
    },
    {
      "exhibition_time_weight": 12,
      "exhibition_st_weight": 2,
      "f_penalty": 4,
      "top1_accuracy_pct": 52.1,
      "improvement_vs_baseline_pt": 2.1
    },
    {
      "exhibition_time_weight": 10,
      "exhibition_st_weight": 8,
      "f_penalty": 4,
      "top1_accuracy_pct": 52.1,
      "improvement_vs_baseline_pt": 2.1
    },
    {
      "exhibition_time_weight": 12,
      "exhibition_st_weight": 2,
      "f_penalty": 8,
      "top1_accuracy_pct": 52.1,
      "improvement_vs_baseline_pt": 2.1
    },
    {
      "exhibition_time_weight": 10,
      "exhibition_st_weight": 8,
      "f_penalty": 6,
      "top1_accuracy_pct": 52.1,
      "improvement_vs_baseline_pt": 2.1
    }
  ]
}
```

