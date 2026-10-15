# 直前情報5項目 個別答え合わせ

対象日：2026/10/15

## 取得カバレッジ

- exhibition_time: 683
- exhibition_st: 683
- exhibition_f: 684
- exhibition_course: 683
- course_changed: 683
- wind_speed: 684
- wind_direction: 642
- wave_height: 684

## 個別要素分析

```json
{
  "exhibition_time": {
    "available": true,
    "races": 114,
    "best_win_rate_pct": 31.6,
    "best_top3_rate_pct": 62.3,
    "worst_win_rate_pct": 8.8,
    "mean_within_race_spearman": 0.1375
  },
  "exhibition_st": {
    "available": true,
    "races": 86,
    "best_win_rate_pct": 16.3,
    "best_top3_rate_pct": 54.7,
    "worst_win_rate_pct": 10.5,
    "mean_within_race_spearman": 0.0453
  },
  "exhibition_f": {
    "available": true,
    "boats": 684,
    "flagged_boats": 171,
    "flagged_win_rate_pct": 18.1,
    "flagged_top3_rate_pct": 52.6,
    "unflagged_win_rate_pct": 16.2,
    "unflagged_top3_rate_pct": 49.1
  },
  "course_changed": {
    "available": true,
    "boats": 683,
    "flagged_boats": 54,
    "flagged_win_rate_pct": 5.6,
    "flagged_top3_rate_pct": 40.7,
    "unflagged_win_rate_pct": 17.6,
    "unflagged_top3_rate_pct": 50.9
  }
}
```

## 風速別

```json
[
  {
    "bucket": "0-2m",
    "races": 79,
    "boat1_win_rate_pct": 63.3
  },
  {
    "bucket": "3-4m",
    "races": 35,
    "boat1_win_rate_pct": 60.0
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
  "races": 156,
  "baseline_top1_accuracy_pct": 59.0,
  "best_candidates": [
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 4,
      "f_penalty": 0,
      "top1_accuracy_pct": 60.3,
      "improvement_vs_baseline_pt": 1.3
    },
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 4,
      "f_penalty": 2,
      "top1_accuracy_pct": 60.3,
      "improvement_vs_baseline_pt": 1.3
    },
    {
      "exhibition_time_weight": 8,
      "exhibition_st_weight": 2,
      "f_penalty": 2,
      "top1_accuracy_pct": 60.3,
      "improvement_vs_baseline_pt": 1.3
    },
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 4,
      "f_penalty": 4,
      "top1_accuracy_pct": 60.3,
      "improvement_vs_baseline_pt": 1.3
    },
    {
      "exhibition_time_weight": 8,
      "exhibition_st_weight": 2,
      "f_penalty": 4,
      "top1_accuracy_pct": 60.3,
      "improvement_vs_baseline_pt": 1.3
    },
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 4,
      "f_penalty": 6,
      "top1_accuracy_pct": 60.3,
      "improvement_vs_baseline_pt": 1.3
    },
    {
      "exhibition_time_weight": 8,
      "exhibition_st_weight": 2,
      "f_penalty": 6,
      "top1_accuracy_pct": 60.3,
      "improvement_vs_baseline_pt": 1.3
    },
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 4,
      "f_penalty": 8,
      "top1_accuracy_pct": 60.3,
      "improvement_vs_baseline_pt": 1.3
    },
    {
      "exhibition_time_weight": 8,
      "exhibition_st_weight": 2,
      "f_penalty": 8,
      "top1_accuracy_pct": 60.3,
      "improvement_vs_baseline_pt": 1.3
    },
    {
      "exhibition_time_weight": 10,
      "exhibition_st_weight": 0,
      "f_penalty": 8,
      "top1_accuracy_pct": 60.3,
      "improvement_vs_baseline_pt": 1.3
    }
  ]
}
```

