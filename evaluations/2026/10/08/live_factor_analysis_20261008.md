# 直前情報5項目 個別答え合わせ

対象日：2026/10/08

## 取得カバレッジ

- exhibition_time: 853
- exhibition_st: 853
- exhibition_f: 854
- exhibition_course: 853
- course_changed: 853
- wind_speed: 854
- wind_direction: 782
- wave_height: 854

## 個別要素分析

```json
{
  "exhibition_time": {
    "available": true,
    "races": 142,
    "best_win_rate_pct": 29.6,
    "best_top3_rate_pct": 63.4,
    "worst_win_rate_pct": 11.3,
    "mean_within_race_spearman": 0.2184
  },
  "exhibition_st": {
    "available": true,
    "races": 107,
    "best_win_rate_pct": 28.0,
    "best_top3_rate_pct": 59.8,
    "worst_win_rate_pct": 15.9,
    "mean_within_race_spearman": 0.0547
  },
  "exhibition_f": {
    "available": true,
    "boats": 854,
    "flagged_boats": 207,
    "flagged_win_rate_pct": 18.4,
    "flagged_top3_rate_pct": 52.2,
    "unflagged_win_rate_pct": 16.2,
    "unflagged_top3_rate_pct": 49.5
  },
  "course_changed": {
    "available": true,
    "boats": 853,
    "flagged_boats": 55,
    "flagged_win_rate_pct": 9.1,
    "flagged_top3_rate_pct": 45.5,
    "unflagged_win_rate_pct": 17.3,
    "unflagged_top3_rate_pct": 50.5
  }
}
```

## 風速別

```json
[
  {
    "bucket": "0-2m",
    "races": 91,
    "boat1_win_rate_pct": 64.8
  },
  {
    "bucket": "3-4m",
    "races": 49,
    "boat1_win_rate_pct": 61.2
  },
  {
    "bucket": "5m以上",
    "races": 3,
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
  "races": 142,
  "baseline_top1_accuracy_pct": 49.3,
  "best_candidates": [
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 0,
      "f_penalty": 4,
      "top1_accuracy_pct": 52.1,
      "improvement_vs_baseline_pt": 2.8
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 8,
      "f_penalty": 0,
      "top1_accuracy_pct": 52.1,
      "improvement_vs_baseline_pt": 2.8
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 8,
      "f_penalty": 2,
      "top1_accuracy_pct": 52.1,
      "improvement_vs_baseline_pt": 2.8
    },
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 10,
      "f_penalty": 0,
      "top1_accuracy_pct": 52.1,
      "improvement_vs_baseline_pt": 2.8
    },
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 0,
      "f_penalty": 0,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 2.1
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 6,
      "f_penalty": 0,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 2.1
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 0,
      "f_penalty": 4,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 2.1
    },
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 0,
      "f_penalty": 2,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 2.1
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 6,
      "f_penalty": 2,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 2.1
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 8,
      "f_penalty": 0,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 2.1
    }
  ]
}
```

