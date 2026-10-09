# 唐津10Rの雷神「未発動」誤表示 — 原因・準備済み修正・未実行確認

## 作業境界

**ユーザー指示：調査・修正案準備まで。本番への適用、ワークフロー実行、過去予測の再生成、家族ページ公開は実行しない。**
対象: 2026-10-09 唐津10R / race_id=20261009-23-10 / 締切13:17 JST。
この検証ブランチは**未マージ**であり、作成した回帰テストも未実行。実行許可後に事前テスト、正本照合、公開まで段階的に実施する。

## 根拠となる正本と食い違い

- `predictions/2026/10/09/live/formation_predictions_final_20261009.json` の13:22:10版では、唐津10Rの `prediction_quality.status=fallback`、`recovery_needed=true`、`up_signal.available=false`、`up_signal.level=0`、`suppressed_reason=fallback_prediction`。専用24点なし。これは**未発動ではなく判定不可**。
- `predictions/2026/10/09/live/live_predictions_final_20261009.json` の13:22版に唐津10Rが存在しなかったため、共通予測正本に公式直前スコアが入らず朝代替となった。
- その後 `evaluations/2026/10/09/recovery/official_retry_beforeinfo_entries_20261009.csv` に保存された唐津10Rの公式 `beforeinfo` 証拠は13:24:29取得。締切時刻13:17より後。
- `evaluations/2026/10/09/recovery/merged_live_predictions_20261009.csv` に13:24:34生成の唐津10R復元6艇スコアが保存された。manifestは `status=complete`、`result_leakage=false`、`treat_recovered_as_observation=true`、`recovered_races` に対象Rを掲載。
- 復元スコア: 2号艇86.24(+1.94)、1号艇68.24(+4.94)、3号艇67.04(+3.74)、4号艇55.68(+3.58)、5号艇36.08-26.10=+9.98(5位)、6号艇20.32-10.90=+9.42(6位)。
- 現行雷神基準は直前4位以下で朝比+7.5点以上。5・6号艇が該当。**Lv1**（最大の実数値+9.98はLv2の10.00未満）。風神Lv0。専用AI種別は **F0R1・24点**。
- 画面 `build_family_race_compare_page.py` は復元CSVから直前6艇スコアを表示できる一方、シグナル表示は `formation_predictions_final` のシグナル欄のみを参照する。この「復元表示と未同期の正本」のズレが矛盾を生んだ。
- さらに従来の `signal_payout_badge` は、シグナルの `available=false` を確認せず `level=0` だけで「5千円以上・未発動」と表示した。

## データ同期しなかった直接要因

- `.github/workflows/intraday_compare.yml` は復旧分析CSV・manifestをGitHubへコミットし、**直接家族ページ再発行**を実行していた。
- `.github/workflows/canonical_recovery_reconcile.yml` は復旧CSVの`push`経由で起動するつもりだったが、通常の`GITHUB_TOKEN`で発生したGitHub Actions内pushは原則別のpush workflowを自動トリガーしない。結果として13:24の復元が共通正本に反映されなかった。
- `canonical_recovery_reconcile.yml` はワークフロー完了時に家族ページを連動させる既存の仕組みがある。**必要なのは復旧処理を毎回明示的に呼ぶ入口の修正**で、独立の再計算ロジックは増やさない。

## 検証ブランチで準備した変更

1. `.github/workflows/intraday_compare.yml`：事後復元manifestがある場合、結果保存後に `gh workflow run canonical_recovery_reconcile.yml --ref main -f target_date=$TARGET_DATE` を明示的に呼ぶ。これが正本再生成と24点監査・書込みを行い、成功時の`workflow_run`で家族ページが再公開される。manifestがない場合のみ従来どおり家族ページを起動。
2. `collectors/build_family_race_compare_page.py`：`signal_payout_badge`の判定を明確化。スコアが観測できていないレースは「5千円以上・未判定」、真正に観測した結果の非発動だけを「未発動」、後日復元による発動は「5千円以上・事後捕捉」と明示する。
3. `tests/test_karatsu10_signal_recovery.py`：公式復元6艇、5・6号艇対象、F0R1、専用24点、未判定/未発動/事後捕捉の区別、ワークフロー明示起動の回帰テストを追加（**実行していない**）。

## 実行許可後の確認手順（現時点では実行禁止）

1. 検証ブランチの差分と現在のmainとの差分を再確認し、本番mainの途中更新を取り込む。
2. `python -m unittest discover -s tests -p test_karatsu10_signal_recovery.py -v` 等の回帰・既存契約テスト、家族表示の差分テストを実行。
3. GitHub Actionsテスト成功・競合なしを確認後、PRをmainへマージする。**勝手にマージしない**。
4. **ユーザーからの別途実行指示後**、対象日20261009だけの `canonical_recovery_reconcile.yml` を実行し、唐津10Rで `up_signal.available=true`、`level=1`、候補艇5と6、`signal_ai_prediction.signal_key=F0R1`、`combinations=24` を保存確認。
5. 同じ保存レコードのシグナルが「最新情報」「レース照合」「結果成績」「AI分析」に一貫して使用されること、雷神の捕捉率と24点シミュレーションで同じ1レースが分母に加算されることを照合。
6. 通常フォーメーション／通常AI8点／当時の購入履歴は変更しない。事後復元であることを `retrospective_signal_recovery` と `signal_detected_at_original_deadline=false` で区別する。
7. 公開ページが「5千円以上・事後捕捉」等の正しい区分で表示されるか確認し、他レースで「未判定」を「未発動」と数えないことを検証。

## 絶対に避けること

- 復旧CSVを画面で直接再計算して、共通予測正本とは別の風神雷神ロジックを作らない。
- 事後取得した公式beforeinfoを「締切時点で取得・賭け済み」と偽らない。
- +9.98を四捨五入した+10.0でLv2に格上げしない。
- 同期が完了していないのに解析率・未捕捉率・回収率の母数へ「未発動」として算入しない。
