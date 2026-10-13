# PDCA 01｜データ収集・完全性監査（2026-10-13）

- 確認日: 2026-10-14 JST
- 対象: 2026-10-13 11場 132レース
- 判定: **研究データのレース単位完全性 PASS。ただし自動取得稼働と「締切前生成」証拠の完全性は別評価として継続検証。**
- 本番予測、採用シグナル、買い目、係数は本監査で変更していない。

## 1. 収集・照合実数

| 検査対象 | 保存数 | 判定 |
|---|---:|---|
| 開催番組 | 132 R / 132 R | PASS |
| 公式3連単・払戻・着順 | 132 R / 132 R | PASS |
| 公式選手別着順データ | 792行 = 132×6 | PASS（着順・登録番号） |
| 朝予測（6艇） | 792行 / 132R | PASS |
| 初期直前予測正本 | 672行 / 112R | 初期保管として記録 |
| 復元の対象 | 24R / 143行（1艇展示不参加） | 回復処理を監査 |
| 復元後の研究用直前予測 | 791行 / 132R | 条件付きPASS、後述 |
| 実績との予測照合 | 朝132R・直前132R | PASS（研究用） |
| 風神雷神シグナル整合 | 132R / 132R、発動114・非発動18 | PASS（保存データ） |

結果R IDは番組132件に完全一致、追加・欠落R IDなし。公式艇別結果はすべて6艇分、直前予測は重複登録番号なし。出走登録番号は復元後の直前予測791行すべて番組表と一致した。

## 2. 24対象 vs 20追加と、1艇の例外

- 復元manifest `missing_before` / `recovered_races` は24R。
- 初期直前予測112Rに既に存在していた4レース：`202610130406`, `202610131105`, `202610131212`, `202610131905`。
- ユニークな研究用直前予測レースは **112+24-4=132R**。完全性監査 `original_pre_race_complete_races=112`, `post_result_recovered_complete_races=20` と定義上矛盾しない。
- 鳴門8R `202610131408` の3号艇・登録番号5201は、元の公式beforeinfoスナップショット（11:29取得）および翌日00:19再取得でともに `is_miss=True`、展示欄欠測。公式着順CSVには3号艇の6着がある。**展示不参加（記録上のmiss）という合法的例外であり取得失敗と誤判定しない**。
- 鳴門8Rは公式出走・着順6艇に対し、直前**展示スコア付与対象5艇**。保存済みの研究用比較ではこの例外を明示し、展示データのない3号艇を架空の値で補わない。

## 3. 重要な留保・別監査

### 直前の時刻・来歴
- 初期直前CSV112Rのうち、行の `generated_at` が番組締切より前：63R、締切より後：49R。
- 復元後CSV132Rは、締切より前：63R、後：69R。
- **generated_atは予測ファイルの生成時刻であり、元情報を収集した時刻と同一ではない。** よって「締切後生成＝結果を使った」とも「112件すべて締切前に最終予想として公開された」とも断定できない。
- 取得元beforeinfoの `collected_at`、予測ファイルの `generated_at`、実際の公開時刻、レース締切をレースIDごとに別々に保持・突合する監査を継続。結果・払戻が予測入力に使われた証拠は今回なし。研究再構成は実購入実績ではない。

### 手動研究モード
- 日次品質監査の `collection_mode=manual_research`、`automatic_collection_enabled=false`。今回の132R完全性PASSは**自動取得の安定稼働を証明しない**。

### 公式結果の補助フィールド
- `archive/2026/10/13/boat_results_20261013_all.csv` は艇別6艇×132Rの `finish` が全件存在する一方、実戦 `course`・`st`・`race_time` 列は各792行すべて空欄。
- 3連単着順・払戻・1〜3着の正誤検証には影響しないが、**実戦STや実進入を直接検証する研究には不足**。展示ST・展示進入と混同しない。

### シグナル表示整合性
- `signal_display_consistency_20261013.json`：status PASS、validated 132、発動114、非発動18、inconsistencies 0。
- データ出典内訳：saved_live 101R、saved_pre_deadline_official_beforeinfo 7R、post_result_official_beforeinfo 24R。
- この「事後公式データ出典24R」は完全性監査の「研究用新規追加20R」と**集計の観点が異なる**ため混ぜない。
- `public_page_checked=false` なので公開サイト画面の反映の一致は未検証。保存データのPASSをサイト表示PASSと取り違えない。

## 4. 原因評価と恒久的な監査改善案

1. **展示不参加フラグを第一優先**：6名の出走予定・公式着順は保持し、展示スコアの行数が5の場合は `is_miss=True` に照合する。理由のない5行は警告。6行に水増ししない。
2. **取得→計算→公開の時刻分離**：レース毎に原データの `collected_at`、各予想版の `generated_at`、公開済みコミット/配信時刻、締切を保存し、回収した原本の事後再計算とリアルタイム予測成績を分離する。
3. **公式の実戦ST・進入・レースタイムは別ソース取得可否を確認**。取得できない場合は当該要素のPDCAに使用しない。
4. **判定を分割**：「レース収集完全性」「研究用シグナル妥当性」「リアルタイム予測再現性」「自動取得稼働」「公開ページ反映」をそれぞれPASS/WARN/FAILで表示する。
5. 復元20Rの原データ使用を継続しつつ、**結果・払戻はスコア生成処理に入れない**。当日の元予測を事後再構成で上書きしない。

## 5. Check / Act

- **研究用データのレース網羅性：採用（PASS）**。全132Rの通常精度比較に進める。復元データは観測時刻区分を必ず添付。
- **鳴門8Rの展示5艇：公式is_miss例外（正常）**、ただし6艇スコア完全性の分母から除外または別表示する。真の欠損と呼ばない。
- **実戦ST/進入/レースタイム：継続検証**。公式結果CSVの補助列を埋めずに実戦ST効果の結論を出さない。
- **本番締切前予測の確認と自動取得稼働：継続検証**。生成時刻後付けや手動再取得と区別できる資料で検証。
- **保存シグナル照合：PASS、公開画面一致：未確認**。サイト側は別途ブラウザで照合する。
- **次の目次：第2項「朝予測・直前予測の精度」**に進行可能。ただし研究復元データをリアルタイム成績と偽らない。

## 根拠ソース
- [番組全132R](https://github.com/lifeworks5783-gif/-boatrace-ai/blob/main/daily_inputs/2026/10/13/base/program_races_20261013.csv)
- [公式3連単・払戻](https://github.com/lifeworks5783-gif/-boatrace-ai/blob/main/archive/2026/10/13/results_20261013_all.csv)
- [公式着順艇別](https://github.com/lifeworks5783-gif/-boatrace-ai/blob/main/archive/2026/10/13/boat_results_20261013_all.csv)
- [朝予測正本](https://github.com/lifeworks5783-gif/-boatrace-ai/blob/main/predictions/2026/10/13/morning_predictions_20261013.csv)
- [直前予測保存](https://github.com/lifeworks5783-gif/-boatrace-ai/blob/main/predictions/2026/10/13/live/live_predictions_final_20261013.csv)
- [研究用直前予測統合](https://github.com/lifeworks5783-gif/-boatrace-ai/blob/main/evaluations/2026/10/13/recovery/merged_live_predictions_20261013.csv)
- [完備監査](https://github.com/lifeworks5783-gif/-boatrace-ai/blob/main/evaluations/2026/10/13/data_quality/completeness_20261013.json)
- [復元manifest](https://github.com/lifeworks5783-gif/-boatrace-ai/blob/main/evaluations/2026/10/13/recovery/live_recovery_manifest_20261013.json)
- [11:29取得・鳴門8R艇3の展示不参加](https://github.com/lifeworks5783-gif/-boatrace-ai/blob/main/daily_inputs/2026/10/13/live/v4_decoded/20261013_113025/beforeinfo_entries_20261013.csv)
- [公式再取得・同一展示不参加](https://github.com/lifeworks5783-gif/-boatrace-ai/blob/main/evaluations/2026/10/13/recovery/official_retry_beforeinfo_entries_20261013.csv)
- [シグナル監査](https://github.com/lifeworks5783-gif/-boatrace-ai/blob/main/evaluations/2026/10/13/data_quality/signal_display_consistency_20261013.json)
- [予測精度監査](https://github.com/lifeworks5783-gif/-boatrace-ai/blob/main/evaluations/2026/10/13/prediction_evaluation_20261013.json)
