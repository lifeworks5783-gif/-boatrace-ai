# 直前情報5項目 個別答え合わせ

対象日：2026/09/30

## 取得カバレッジ

- exhibition_time: 818
- exhibition_st: 854
- exhibition_f: 854
- exhibition_course: 818
- course_changed: 854
- wind_speed: 0
- wind_direction: 818
- wave_height: 0

## 個別要素分析

```json
{
  "exhibition_time": {
    "available": true,
    "races": 137,
    "best_win_rate_pct": 35.0,
    "best_top3_rate_pct": 67.9,
    "worst_win_rate_pct": 8.8,
    "mean_within_race_spearman": 0.1971
  },
  "exhibition_st": {
    "available": true,
    "races": 143,
    "best_win_rate_pct": 18.2,
    "best_top3_rate_pct": 56.6,
    "worst_win_rate_pct": 14.0,
    "mean_within_race_spearman": 0.0341
  },
  "exhibition_f": {
    "available": true,
    "boats": 854,
    "flagged_boats": 0,
    "flagged_win_rate_pct": null,
    "flagged_top3_rate_pct": null,
    "unflagged_win_rate_pct": 16.9,
    "unflagged_top3_rate_pct": 50.6
  },
  "course_changed": {
    "available": true,
    "boats": 854,
    "flagged_boats": 53,
    "flagged_win_rate_pct": 15.1,
    "flagged_top3_rate_pct": 47.2,
    "unflagged_win_rate_pct": 17.0,
    "unflagged_top3_rate_pct": 50.8
  }
}
```

## 風速別

```json
[]
```

## 展示タイム・ST・F 重み探索

```json
{
  "available": true,
  "available_factors": [
    "exhibition_time",
    "exhibition_st"
  ],
  "races": 137,
  "baseline_top1_accuracy_pct": 54.7,
  "best_candidates": [
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 2,
      "f_penalty": 0,
      "top1_accuracy_pct": 56.2,
      "improvement_vs_baseline_pt": 1.5
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 2,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.7,
      "improvement_vs_baseline_pt": 0.0
    },
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 2,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.7,
      "improvement_vs_baseline_pt": 0.0
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 0,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.0,
      "improvement_vs_baseline_pt": -0.7
    },
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 0,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.0,
      "improvement_vs_baseline_pt": -0.7
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 4,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.0,
      "improvement_vs_baseline_pt": -0.7
    },
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 2,
      "f_penalty": 0,
      "top1_accuracy_pct": 54.0,
      "improvement_vs_baseline_pt": -0.7
    },
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 0,
      "f_penalty": 0,
      "top1_accuracy_pct": 53.3,
      "improvement_vs_baseline_pt": -1.5
    },
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 4,
      "f_penalty": 0,
      "top1_accuracy_pct": 53.3,
      "improvement_vs_baseline_pt": -1.5
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 10,
      "f_penalty": 0,
      "top1_accuracy_pct": 53.3,
      "improvement_vs_baseline_pt": -1.5
    }
  ]
}
```

