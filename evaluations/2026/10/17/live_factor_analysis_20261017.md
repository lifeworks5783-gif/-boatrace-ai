# 直前情報5項目 個別答え合わせ

対象日：2026/10/17

## 取得カバレッジ

- exhibition_time: 832
- exhibition_st: 833
- exhibition_f: 834
- exhibition_course: 833
- course_changed: 833
- wind_speed: 834
- wind_direction: 798
- wave_height: 834

## 個別要素分析

```json
{
  "exhibition_time": {
    "available": true,
    "races": 139,
    "best_win_rate_pct": 33.8,
    "best_top3_rate_pct": 58.3,
    "worst_win_rate_pct": 9.4,
    "mean_within_race_spearman": 0.131
  },
  "exhibition_st": {
    "available": true,
    "races": 107,
    "best_win_rate_pct": 16.8,
    "best_top3_rate_pct": 55.1,
    "worst_win_rate_pct": 13.1,
    "mean_within_race_spearman": 0.1128
  },
  "exhibition_f": {
    "available": true,
    "boats": 834,
    "flagged_boats": 210,
    "flagged_win_rate_pct": 19.0,
    "flagged_top3_rate_pct": 52.4,
    "unflagged_win_rate_pct": 15.9,
    "unflagged_top3_rate_pct": 49.2
  },
  "course_changed": {
    "available": true,
    "boats": 833,
    "flagged_boats": 49,
    "flagged_win_rate_pct": 8.2,
    "flagged_top3_rate_pct": 40.8,
    "unflagged_win_rate_pct": 17.2,
    "unflagged_top3_rate_pct": 50.6
  }
}
```

## 風速別

```json
[
  {
    "bucket": "0-2m",
    "races": 64,
    "boat1_win_rate_pct": 53.1
  },
  {
    "bucket": "3-4m",
    "races": 63,
    "boat1_win_rate_pct": 49.2
  },
  {
    "bucket": "5m以上",
    "races": 12,
    "boat1_win_rate_pct": 33.3
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
  "baseline_top1_accuracy_pct": 48.8,
  "best_candidates": [
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 6,
      "f_penalty": 0,
      "top1_accuracy_pct": 50.0,
      "improvement_vs_baseline_pt": 1.2
    },
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 6,
      "f_penalty": 0,
      "top1_accuracy_pct": 50.0,
      "improvement_vs_baseline_pt": 1.2
    },
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 8,
      "f_penalty": 0,
      "top1_accuracy_pct": 50.0,
      "improvement_vs_baseline_pt": 1.2
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 2,
      "f_penalty": 0,
      "top1_accuracy_pct": 49.4,
      "improvement_vs_baseline_pt": 0.6
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 0,
      "f_penalty": 0,
      "top1_accuracy_pct": 49.4,
      "improvement_vs_baseline_pt": 0.6
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 2,
      "f_penalty": 0,
      "top1_accuracy_pct": 49.4,
      "improvement_vs_baseline_pt": 0.6
    },
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 0,
      "f_penalty": 0,
      "top1_accuracy_pct": 49.4,
      "improvement_vs_baseline_pt": 0.6
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 4,
      "f_penalty": 0,
      "top1_accuracy_pct": 49.4,
      "improvement_vs_baseline_pt": 0.6
    },
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 2,
      "f_penalty": 0,
      "top1_accuracy_pct": 49.4,
      "improvement_vs_baseline_pt": 0.6
    },
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 4,
      "f_penalty": 0,
      "top1_accuracy_pct": 49.4,
      "improvement_vs_baseline_pt": 0.6
    }
  ]
}
```

