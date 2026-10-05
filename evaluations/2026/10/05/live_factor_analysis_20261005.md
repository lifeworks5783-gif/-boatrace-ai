# 直前情報5項目 個別答え合わせ

対象日：2026/10/05

## 取得カバレッジ

- exhibition_time: 863
- exhibition_st: 863
- exhibition_f: 864
- exhibition_course: 863
- course_changed: 863
- wind_speed: 864
- wind_direction: 708
- wave_height: 864

## 個別要素分析

```json
{
  "exhibition_time": {
    "available": true,
    "races": 144,
    "best_win_rate_pct": 36.8,
    "best_top3_rate_pct": 70.8,
    "worst_win_rate_pct": 6.2,
    "mean_within_race_spearman": 0.2256
  },
  "exhibition_st": {
    "available": true,
    "races": 124,
    "best_win_rate_pct": 25.0,
    "best_top3_rate_pct": 57.3,
    "worst_win_rate_pct": 15.3,
    "mean_within_race_spearman": 0.1
  },
  "exhibition_f": {
    "available": true,
    "boats": 864,
    "flagged_boats": 148,
    "flagged_win_rate_pct": 18.9,
    "flagged_top3_rate_pct": 50.7,
    "unflagged_win_rate_pct": 16.2,
    "unflagged_top3_rate_pct": 49.9
  },
  "course_changed": {
    "available": true,
    "boats": 863,
    "flagged_boats": 52,
    "flagged_win_rate_pct": 5.8,
    "flagged_top3_rate_pct": 30.8,
    "unflagged_win_rate_pct": 17.4,
    "unflagged_top3_rate_pct": 51.3
  }
}
```

## 風速別

```json
[
  {
    "bucket": "0-2m",
    "races": 109,
    "boat1_win_rate_pct": 60.6
  },
  {
    "bucket": "3-4m",
    "races": 34,
    "boat1_win_rate_pct": 52.9
  },
  {
    "bucket": "5m以上",
    "races": 1,
    "boat1_win_rate_pct": 0.0
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
  "baseline_top1_accuracy_pct": 47.9,
  "best_candidates": [
    {
      "exhibition_time_weight": 10,
      "exhibition_st_weight": 0,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.9,
      "improvement_vs_baseline_pt": 6.9
    },
    {
      "exhibition_time_weight": 10,
      "exhibition_st_weight": 2,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.9,
      "improvement_vs_baseline_pt": 6.9
    },
    {
      "exhibition_time_weight": 12,
      "exhibition_st_weight": 0,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.9,
      "improvement_vs_baseline_pt": 6.9
    },
    {
      "exhibition_time_weight": 12,
      "exhibition_st_weight": 2,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.9,
      "improvement_vs_baseline_pt": 6.9
    },
    {
      "exhibition_time_weight": 8,
      "exhibition_st_weight": 0,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.2,
      "improvement_vs_baseline_pt": 6.2
    },
    {
      "exhibition_time_weight": 8,
      "exhibition_st_weight": 0,
      "f_penalty": 2,
      "top1_accuracy_pct": 54.2,
      "improvement_vs_baseline_pt": 6.2
    },
    {
      "exhibition_time_weight": 10,
      "exhibition_st_weight": 2,
      "f_penalty": 2,
      "top1_accuracy_pct": 54.2,
      "improvement_vs_baseline_pt": 6.2
    },
    {
      "exhibition_time_weight": 10,
      "exhibition_st_weight": 4,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.2,
      "improvement_vs_baseline_pt": 6.2
    },
    {
      "exhibition_time_weight": 12,
      "exhibition_st_weight": 0,
      "f_penalty": 2,
      "top1_accuracy_pct": 54.2,
      "improvement_vs_baseline_pt": 6.2
    },
    {
      "exhibition_time_weight": 12,
      "exhibition_st_weight": 2,
      "f_penalty": 2,
      "top1_accuracy_pct": 54.2,
      "improvement_vs_baseline_pt": 6.2
    }
  ]
}
```

