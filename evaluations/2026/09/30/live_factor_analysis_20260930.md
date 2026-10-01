# 直前情報5項目 個別答え合わせ

対象日：2026/09/30

## 取得カバレッジ

- exhibition_time: 828
- exhibition_st: 864
- exhibition_f: 864
- exhibition_course: 828
- course_changed: 864
- wind_speed: 0
- wind_direction: 828
- wave_height: 0

## 個別要素分析

```json
{
  "exhibition_time": {
    "available": true,
    "races": 138,
    "best_win_rate_pct": 34.1,
    "best_top3_rate_pct": 63.8,
    "worst_win_rate_pct": 8.7,
    "mean_within_race_spearman": 0.1733
  },
  "exhibition_st": {
    "available": true,
    "races": 144,
    "best_win_rate_pct": 18.1,
    "best_top3_rate_pct": 56.2,
    "worst_win_rate_pct": 13.9,
    "mean_within_race_spearman": 0.0471
  },
  "exhibition_f": {
    "available": true,
    "boats": 864,
    "flagged_boats": 0,
    "flagged_win_rate_pct": null,
    "flagged_top3_rate_pct": null,
    "unflagged_win_rate_pct": 16.7,
    "unflagged_top3_rate_pct": 50.0
  },
  "course_changed": {
    "available": true,
    "boats": 864,
    "flagged_boats": 54,
    "flagged_win_rate_pct": 14.8,
    "flagged_top3_rate_pct": 46.3,
    "unflagged_win_rate_pct": 16.8,
    "unflagged_top3_rate_pct": 50.2
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
  "races": 138,
  "baseline_top1_accuracy_pct": 53.6,
  "best_candidates": [
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 2,
      "f_penalty": 0,
      "top1_accuracy_pct": 55.1,
      "improvement_vs_baseline_pt": 1.4
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 2,
      "f_penalty": 0,
      "top1_accuracy_pct": 53.6,
      "improvement_vs_baseline_pt": 0.0
    },
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 2,
      "f_penalty": 0,
      "top1_accuracy_pct": 53.6,
      "improvement_vs_baseline_pt": 0.0
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 0,
      "f_penalty": 0,
      "top1_accuracy_pct": 52.9,
      "improvement_vs_baseline_pt": -0.7
    },
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 0,
      "f_penalty": 0,
      "top1_accuracy_pct": 52.9,
      "improvement_vs_baseline_pt": -0.7
    },
    {
      "exhibition_time_weight": 2,
      "exhibition_st_weight": 4,
      "f_penalty": 0,
      "top1_accuracy_pct": 52.9,
      "improvement_vs_baseline_pt": -0.7
    },
    {
      "exhibition_time_weight": 4,
      "exhibition_st_weight": 4,
      "f_penalty": 0,
      "top1_accuracy_pct": 52.9,
      "improvement_vs_baseline_pt": -0.7
    },
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 2,
      "f_penalty": 0,
      "top1_accuracy_pct": 52.9,
      "improvement_vs_baseline_pt": -0.7
    },
    {
      "exhibition_time_weight": 6,
      "exhibition_st_weight": 0,
      "f_penalty": 0,
      "top1_accuracy_pct": 52.2,
      "improvement_vs_baseline_pt": -1.4
    },
    {
      "exhibition_time_weight": 0,
      "exhibition_st_weight": 10,
      "f_penalty": 0,
      "top1_accuracy_pct": 52.2,
      "improvement_vs_baseline_pt": -1.4
    }
  ]
}
```

