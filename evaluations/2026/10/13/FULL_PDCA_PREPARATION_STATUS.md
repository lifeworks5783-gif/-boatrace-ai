# 2026-10-13 フルPDCA準備・実行検証チェック

## 状況（2026-10-14確認）
- **準備コード：コミット済み**
- **実行トリガー：コミット済み** `config/run_saved_pdca_20261013.txt`
- **処理完了・結果ファイル生成：未確認**（GitHub Actionsの実行ログを取得できていないため、実行・成功とは断定しない）
- 本番予測、買い目、風神雷神の採用係数はこの準備作業で変更していない。

## 監査済み公式データ
- 開催番組：132/132
- 公式結果：132/132、全レースIDが番組と一致
- 公式艇別結果：792行、132レース×6艇、艇別結果の欠落・重複なし
- 公式データ完全性：`evaluations/2026/10/13/data_quality/completeness_20261013.json` = PASS、research_status = PASS
- 直前取得：元の正本112R、追加入力から集計可能132R。
- 復元manifestの24Rと監査の20Rの差は、対象4R (202610130406,202610131105,202610131212,202610131905) が元の直前予測ファイルに6艇分ずつ存在した重複によるもの。復元対象24Rと追加集計対象20Rは母数の定義が異なるため、研究用の元データ採用件数と観測件数を別々に扱う。
- 公式収集時刻・後日再構成フラグを保持し、事前予測・事後復元を混同しない。

## 今回の追加処理
1. `collectors/evaluate_signal_pdca_cross.py` に `--raijin-v2` を追加。従来の保存シグナル16×4方式集計と、新雷神V2再構成（独立の16×4方式）を**別ディレクトリ**に書き出す。
   - 従来：`evaluations/signal_pdca_cross/latest/summary.json`
   - 新雷神V2：`evaluations/raijin_v2_signal_pdca_cross/latest/summary.json`
   - V2の専用AI24点はV2独自の `new_actual_rank` で精算し、旧シグナル補正の結果を代用しない。
2. 新雷神V2同一順位の6/8/12/18/24点比較 `collectors/evaluate_raijin_v2_points_pdca.py` を追加。専用AI24点の件数・的中・投資・払戻が再構成正本と一致しない場合は停止。
3. `.github/workflows/saved_data_pdca_refresh.yml` に、両方の16×4集計、V2五段階点数、買い方1/2/3再比較、日別単体要素・直前要素分析を追加。
4. 出力の16区分・4方式・対象日の監査済みレース数をチェックするゲートを設定。F0R0の専用AIは対象外（0%扱い不可）。
5. 評価専用出力をGitHubへ保存する既存フローは維持。実行途中で本番の補正・予測・買い目には触れない。

## 「フルPDCA準備完了」の判定条件
下記ファイルの内容を読み、日別132R・累計モデル別母数・回収率・分類を照合してから準備完了と報告する。
- `evaluations/raijin_all_rank_v2_replay/daily/20261013/summary.json`
- `evaluations/signal_ai/latest/summary.json` の `source_dates` に20261013を含む
- `evaluations/raijin_v2_signal_pdca_cross/latest/summary.json`
- `evaluations/raijin_v2_points_pdca/latest/summary.json`（6/8/12/18/24点、24点の正本一致）
- `evaluations/signal_pdca_cross/latest/summary.json`
- `evaluations/pdca_buying_strategy/latest/summary.json` の最新日
- `evaluations/2026/10/13/score_component_analysis_20261013.json`
- `evaluations/2026/10/13/live_factor_analysis_20261013.json`
- 風神雷神16分類×4方式：旧保存シグナル／新雷神V2を混同せず、当日・直近7日・累計を分離。
- 新雷神V2の6/8/12/18/24点は同じ順位120通りと公式結果で比較し、事後仮想買い目を当時の購入実績と表示しない。

## 結論・次の検証
**PDCAの入力の完全性確認と処理への準備コミットは済み。出力生成・実行成功を未確認のまま完了報告しない。**
