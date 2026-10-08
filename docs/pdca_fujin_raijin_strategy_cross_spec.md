# 風神雷神 × 買い方 クロスPDCA仕様

開始日: 2026-10-08
状態: 2026-10-09 運用方針確定。毎日の夜PDCAで必須集計（予測ロジックへの影響なし）

## 目的
風神Lv0-3 × 雷神Lv0-3 の各組み合わせごとに、どの予測方式・買い方・フォーメーション区分が有効だったかを日次・累積で比較し、将来の買い/見送り判定と買い方選択の根拠にする。

## 固定クロス軸
- シグナル: F0_R0 ～ F3_R3（風神Lv × 雷神Lv）
- 予測段階: 朝 / 直前
- 評価: 1着一致 / TOP3整合 / 完全一致 / 実買い目的中
- 買い方: 通常フォーメーション / 上位3艇BOX6点 / 通常AIスコア8点（実際の点数も併記） / 風神雷神専用シグナルAI24点（検証用、点数別6/8/12/18/24は別列）
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
signal_ai_hit, signal_ai_points, signal_ai_investment, signal_ai_return,
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
- 損益、未評価数と理由、予測・買い方のバージョンと評価可能期間

## PDCA上の扱い
- サンプル不足の組み合わせから採用判断しない。
- 結果は分析専用。通常予測・風神雷神シグナル・AIスコアの外骨格を自動変更しない。
- 結果判明前に保存された予測だけを評価し、結果から予測を再生成しない。
- 将来は「シグナル組み合わせ → 最適買い方 / 見送り」のルール候補作成に使用する。

## 2026-10-09 決定：毎日の夜PDCA必須報告
- F0_R0からF3_R3まで16行を省略しない。該当0件も0件で表示する。
- 4方式の買い方別に、同一レース・同一シグナル判定を結合し、母数、的中、購入点数、投資、払戻、損益、ROIを横比較する。
- 「前日単日」と「同一モデルバージョン・同一ルールの累積」を並べ、前日比・直近7日・日別変動を確認する。方式ごとに評価開始日が異なる場合、必ず期間・母数を別記する。
- F0_R0のシグナル専用AIは原則未適用。「未評価（—）」を0%と混同しない。
- 1着一致、勝者TOP3捕捉、TOP3整合（実着1〜3着の集合一致）、完全一致（着順一致）を混同しない。
- 通常フォーメーションを現行コードの区分（1着固定＋相手流し、準軸、混戦、1・2着固定＋3着流し、1・2着折返し＋3着流し等）別にさらに交差集計する。
- 各方式の実際の買い目と1点100円の仮想購入で清算する。外れた買い目を事後的に差し替えず、予測時点の保存記録と結果の時系列を優先する。
- 当日結果の欠落、欠場艇や5艇立て、後日再構成、保存時刻不明、シグナル未評価は明示して判定母数を揃える。結果発表後に再構成した予測を本番当時の的中として扱わない。
- 低母数・単日高配当への依存・学習期間と検証期間の重複を明記。候補絞り込みはしても、その場で本番ロジック・買い目・シグナル補正を自動変更しない。
- 独立検証まで済んだものだけ「買い/見送り」と買い方候補として提案し、ユーザーの確認を受ける。
- 元データ：`evaluations/fujin_raijin/latest/backtest_details.csv`、`evaluations/signal_ai/latest/details.csv`、日別の`formation_simulation_YYYYMMDD.csv`、`top3_box_simulation_YYYYMMDD.csv`、`ai_score_simulation_YYYYMMDD.csv`、`prediction_evaluation_YYYYMMDD.csv`。
- 毎回GitHub議事録に「単日/累計の16×4集計結果、使用モデルバージョン、未評価件数、次回検証候補」を残す。クロス集計の計算コードと自動実行の整備は、本番予測処理から分離して実装・検証する。
