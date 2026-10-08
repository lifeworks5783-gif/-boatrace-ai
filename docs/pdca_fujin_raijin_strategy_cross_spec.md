# 風神雷神 × 買い方 クロスPDCA仕様

開始日: 2026-10-08
状態: 収集・分析準備済み（予測ロジックへの影響なし）

## 目的
風神Lv0-3 × 雷神Lv0-3 の各組み合わせごとに、どの予測方式・買い方・フォーメーション区分が有効だったかを日次・累積で比較し、将来の買い/見送り判定と買い方選択の根拠にする。

## 固定クロス軸
- シグナル: F0_R0 ～ F3_R3（風神Lv × 雷神Lv）
- 予測段階: 朝 / 直前
- 評価: 1着一致 / TOP3整合 / 完全一致 / 実買い目的中
- 買い方: 通常フォーメーション / BOX / AIスコア予想
- フォーメーション区分: 1着強軸 / 準軸 / 混戦 / その他コード上の現行区分
- シグナル状態: 風神のみ / 雷神のみ / 両方 / なし

## 1レース単位で保存する項目
date, race_id, venue, race,
fujin_level, raijin_level, signal_combo,
morning_winner_hit, morning_top3_hit, morning_exact_hit,
live_winner_hit, live_top3_hit, live_exact_hit,
formation_type, formation_hit, formation_points, formation_investment, formation_return,
box_hit, box_points, box_investment, box_return,
ai_hit, ai_top3_hit, ai_exact_hit, ai_points, ai_investment, ai_return,
trifecta, payout, manshu

## 集計単位
1. signal_combo × prediction/bet method
2. signal_combo × formation_type
3. signal_combo × stage（朝/直前）
4. signal_combo × formation_type × method
5. 日別と全期間累積の両方

## 各集計で必ず出す指標
- 母数
- 的中数・的中率
- 1着一致率
- TOP3整合率
- 完全一致率
- 購入点数
- 投資額
- 払戻額
- 回収率
- 平均払戻
- 万舟件数・万舟率

## PDCA上の扱い
- サンプル不足の組み合わせから採用判断しない。
- 結果は分析専用。通常予測・風神雷神シグナル・AIスコアの外骨格を自動変更しない。
- 結果判明前に保存された予測だけを評価し、結果から予測を再生成しない。
- 将来は「シグナル組み合わせ → 最適買い方 / 見送り」のルール候補作成に使用する。
