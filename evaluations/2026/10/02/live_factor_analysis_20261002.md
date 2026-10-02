# 直前情報5項目 個別答え合わせ

対象日：2026/10/02

## 取得カバレッジ

- exhibition_time: 606
- exhibition_st: 606
- exhibition_f: 606
- exhibition_course: 606
- course_changed: 606
- wind_speed: 606
- wind_direction: 606
- wave_height: 606

## 個別要素分析

```json
{
  "exhibition_time": {
    "available": true,
    "races": 101,
    "best_win_rate_pct": 27.7,
    "best_top3_rate_pct": 63.4,
    "worst_win_rate_pct": 8.9,
    "mean_within_race_spearman": 0.1999
  },
  "exhibition_st": {
    "available": true,
    "races": 81,
    "best_win_rate_pct": 18.5,
    "best_top3_rate_pct": 60.5,
    "worst_win_rate_pct": 4.9,
    "mean_within_race_spearman": 0.1426
  },
  "exhibition_f": {
    "available": true,
    "boats": 606,
    "flagged_boats": 143,
    "flagged_win_rate_pct": 21.7,
    "flagged_top3_rate_pct": 58.0,
    "unflagged_win_rate_pct": 15.1,
    "unflagged_top3_rate_pct": 47.5
  },
  "course_changed": {
    "available": true,
    "boats": 606,
    "flagged_boats": 47,
    "flagged_win_rate_pct": 12.8,
    "flagged_top3_rate_pct": 40.4,
    "unflagged_win_rate_pct": 17.0,
    "unflagged_top3_rate_pct": 50.8
  }
}
```

## 風速別

```json
[
  {
    "bucket": "0-2m",
    "races": 29,
    "boat1_win_rate_pct": 48.3
  },
  {
    "bucket": "3-4m",
    "races": 40,
    "boat1_win_rate_pct": 42.5
  },
  {
    "bucket": "5m以上",
    "races": 32,
    "boat1_win_rate_pct": 43.8
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
  "races": 168,
  "baseline_top1_accuracy_pct": 52.4,
  "best_candidates": [
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 4,
      "f_penalty": 0,
      "top1_accuracy_pct": 55.4,
      "improvement_vs_baseline_pt": 3.0
    },
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 8,
      "f_penalty": 0,
      "top1_accuracy_pct": 55.4,
      "improvement_vs_baseline_pt": 3.0
    },
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 6,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.8,
      "improvement_vs_baseline_pt": 2.4
    },
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 10,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.8,
      "improvement_vs_baseline_pt": 2.4
    },
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 10,
      "f_penalty": 2,
      "top1_accuracy_pct": 54.8,
      "improvement_vs_baseline_pt": 2.4
    },
    {
      "exhibition_time_weight": 8,
      "exhibition_st_weight": 10,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.8,
      "improvement_vs_baseline_pt": 2.4
    },
    {
      "exhibition_time_weight": 8,
      "exhibition_st_weight": 12,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.8,
      "improvement_vs_baseline_pt": 2.4
    },
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 2,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.2,
      "improvement_vs_baseline_pt": 1.8
    },
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 6,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.2,
      "improvement_vs_baseline_pt": 1.8
    },
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 4,
      "f_penalty": 2,
      "top1_accuracy_pct": 54.2,
      "improvement_vs_baseline_pt": 1.8
    }
  ]
}
```

