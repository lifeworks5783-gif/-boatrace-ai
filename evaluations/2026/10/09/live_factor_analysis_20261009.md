# 直前情報5項目 個別答え合わせ

対象日：2026/10/09

## 取得カバレッジ

- exhibition_time: 248
- exhibition_st: 248
- exhibition_f: 248
- exhibition_course: 248
- course_changed: 248
- wind_speed: 248
- wind_direction: 248
- wave_height: 248

## 個別要素分析

```json
{
  "exhibition_time": {
    "available": true,
    "races": 42,
    "best_win_rate_pct": 19.0,
    "best_top3_rate_pct": 52.4,
    "worst_win_rate_pct": 7.1,
    "mean_within_race_spearman": 0.1442
  },
  "exhibition_st": {
    "available": true,
    "races": 37,
    "best_win_rate_pct": 24.3,
    "best_top3_rate_pct": 59.5,
    "worst_win_rate_pct": 13.5,
    "mean_within_race_spearman": 0.0469
  },
  "exhibition_f": {
    "available": true,
    "boats": 248,
    "flagged_boats": 34,
    "flagged_win_rate_pct": 11.8,
    "flagged_top3_rate_pct": 55.9,
    "unflagged_win_rate_pct": 17.8,
    "unflagged_top3_rate_pct": 50.0
  },
  "course_changed": {
    "available": true,
    "boats": 248,
    "flagged_boats": 15,
    "flagged_win_rate_pct": 0.0,
    "flagged_top3_rate_pct": 33.3,
    "unflagged_win_rate_pct": 18.0,
    "unflagged_top3_rate_pct": 51.9
  }
}
```

## 風速別

```json
[
  {
    "bucket": "0-2m",
    "races": 23,
    "boat1_win_rate_pct": 52.2
  },
  {
    "bucket": "3-4m",
    "races": 19,
    "boat1_win_rate_pct": 47.4
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
  "baseline_top1_accuracy_pct": 50.7,
  "best_candidates": [
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 0,
      "f_penalty": 2,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 0.7
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 0,
      "f_penalty": 4,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 0.7
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 2,
      "f_penalty": 2,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 0.7
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 4,
      "f_penalty": 0,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 0.7
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 0,
      "f_penalty": 6,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 0.7
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 2,
      "f_penalty": 4,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 0.7
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 4,
      "f_penalty": 2,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 0.7
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 2,
      "f_penalty": 2,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 0.7
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 0,
      "f_penalty": 8,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 0.7
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 2,
      "f_penalty": 6,
      "top1_accuracy_pct": 51.4,
      "improvement_vs_baseline_pt": 0.7
    }
  ]
}
```

