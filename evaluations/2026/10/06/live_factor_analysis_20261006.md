# 直前情報5項目 個別答え合わせ

対象日：2026/10/06

## 取得カバレッジ

- exhibition_time: 935
- exhibition_st: 935
- exhibition_f: 936
- exhibition_course: 935
- course_changed: 935
- wind_speed: 936
- wind_direction: 906
- wave_height: 936

## 個別要素分析

```json
{
  "exhibition_time": {
    "available": true,
    "races": 156,
    "best_win_rate_pct": 28.8,
    "best_top3_rate_pct": 64.1,
    "worst_win_rate_pct": 10.9,
    "mean_within_race_spearman": 0.2066
  },
  "exhibition_st": {
    "available": true,
    "races": 133,
    "best_win_rate_pct": 17.3,
    "best_top3_rate_pct": 54.9,
    "worst_win_rate_pct": 10.5,
    "mean_within_race_spearman": 0.0417
  },
  "exhibition_f": {
    "available": true,
    "boats": 936,
    "flagged_boats": 171,
    "flagged_win_rate_pct": 21.1,
    "flagged_top3_rate_pct": 51.5,
    "unflagged_win_rate_pct": 15.7,
    "unflagged_top3_rate_pct": 49.7
  },
  "course_changed": {
    "available": true,
    "boats": 935,
    "flagged_boats": 44,
    "flagged_win_rate_pct": 11.4,
    "flagged_top3_rate_pct": 38.6,
    "unflagged_win_rate_pct": 16.9,
    "unflagged_top3_rate_pct": 50.6
  }
}
```

## 風速別

```json
[
  {
    "bucket": "0-2m",
    "races": 57,
    "boat1_win_rate_pct": 64.9
  },
  {
    "bucket": "3-4m",
    "races": 62,
    "boat1_win_rate_pct": 51.6
  },
  {
    "bucket": "5m以上",
    "races": 37,
    "boat1_win_rate_pct": 54.1
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
  "baseline_top1_accuracy_pct": 46.2,
  "best_candidates": [
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 4,
      "f_penalty": 4,
      "top1_accuracy_pct": 48.7,
      "improvement_vs_baseline_pt": 2.6
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 4,
      "f_penalty": 0,
      "top1_accuracy_pct": 48.1,
      "improvement_vs_baseline_pt": 1.9
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 2,
      "f_penalty": 4,
      "top1_accuracy_pct": 48.1,
      "improvement_vs_baseline_pt": 1.9
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 4,
      "f_penalty": 2,
      "top1_accuracy_pct": 48.1,
      "improvement_vs_baseline_pt": 1.9
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 2,
      "f_penalty": 4,
      "top1_accuracy_pct": 48.1,
      "improvement_vs_baseline_pt": 1.9
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 8,
      "f_penalty": 2,
      "top1_accuracy_pct": 48.1,
      "improvement_vs_baseline_pt": 1.9
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 10,
      "f_penalty": 0,
      "top1_accuracy_pct": 48.1,
      "improvement_vs_baseline_pt": 1.9
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 2,
      "f_penalty": 6,
      "top1_accuracy_pct": 48.1,
      "improvement_vs_baseline_pt": 1.9
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 4,
      "f_penalty": 4,
      "top1_accuracy_pct": 48.1,
      "improvement_vs_baseline_pt": 1.9
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 10,
      "f_penalty": 2,
      "top1_accuracy_pct": 48.1,
      "improvement_vs_baseline_pt": 1.9
    }
  ]
}
```

