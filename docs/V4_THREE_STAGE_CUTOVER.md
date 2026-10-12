# V4 三段階自動化・高速収集・旧処理整理（2026-10-12）

## 役割と成果物
1. `.github/workflows/v4_stage1_capture.yml` → `collectors/v4_pipeline.py capture`：朝は公式LZHを保存してから既存番組パーサーへ、直前は最大8並列・時限つき公式HTTP取得。**受信バイト原本は一旦GitHub Actionsの期限つきartifactに保存する。解析成否で取得処理を取り消さない。**
2. `.github/workflows/v4_stage2_decode.yml` → `v4_pipeline.py decode`：直前原本SHA256を再照合してから既存パーサーと例外処理で読取。直前の解析済みCSVだけ日付・時刻スナップショットでGitHubへ保存。問題はstatus.jsonに別記。朝はLZH SHA256を確認後、解析済み番組CSVを保存。
3. `.github/workflows/v4_stage3_predict.yml`：最新の保存済み入力→既存の朝／直前ロジック→通常AI→既存風神雷神・専用AI24点→GitHub保存→家族研究表示の再描画。**収集の再実行、結果データによる予測の再生成、計算式の変更を禁止。** 実際の締切を過ぎてから「当時予測した」と扱わない。

公式サイトの遅延、GitHub Actionsスケジュール遅延による締切前の取得成功は保証できない。空データ・通信失敗・公式欠場・F/L・異常な進入表記は別々にログ記録し、未取得を非発動扱いしない。原本artifactは最大7日で失効し、**Google Drive転送が動くまで永続保存済みとは呼ばない**。

## V3との比較と切替順序
旧：
- `research_live_every_5min.yml`：毎5分、`fast_live_collection_v3.yml`へDispatch
- `fast_live_collection_v3.yml`：前回スナップショット復元・公式読み取り・15～30秒待機再試行・GitHubへ保存・別の直前予測をDispatch
- `live_prediction_0930.yml`：公式収集が含まれる旧単独計算（ボタン再実行互換として当面維持）
- `morning_prediction_daily.yml`：朝の公式取得と予測が混在する旧自動実行
- `research_compare_every_15min.yml`：**結果照合／PDCA**の別用途なので、新V4の収集では置き換えない。

新方式は取得→読み取り→計算を連結し、処理を明確に分離する。1回のActions内で公式サイトへのアクセス後に繰り返しsleepする旧V3を主経路にしない。公式サイトを最大8接続並列化するが、上限付きレース数、対象締切前ウィンドウ、個別タイムアウトで過剰リクエストしない。

切替：
- A: V4のunit/fixture/実公式1ページの原本SHA・パーサーの検証。
- B: cronを有効化する前に、V4 Stage1(朝の既存番組キャッシュ) → Stage2 → Stage3 という**実workflow_runの3連結**をActions実行ログで検証。
- C: 当日まだ締切前のレースでStage1→Stage2→Stage3を確認し、通常AI・風神雷神・24点と表示の既存値に予期せぬ差異がないことを検査。欠損でも他レースを止めない。
- D: V4ライブ5分／朝3:00 JSTのスケジュールを有効にし、旧`research_live_every_5min.yml`のcronと旧`morning_prediction_daily.yml`のcronのみ解除。旧V3・旧手動ボタンは**手動復旧専用の予備**として残す。
- E: 数日分の集計／配信／欠損監査が安定したら、旧定期Dispatchだけでなく未参照・重複した旧ファイルをGitの履歴が残る形で段階的に削除。研究・PDCA用workflowsは別機能なので無条件には破棄しない。

## 工程区切りで記録
- 変更したファイル・PR・merge SHA
- 本物のActions実行番号／ステップ／結論
- 取れた公式原本と解読件数、3段階の引継ぎ成功
- 朝／通常AI／風神雷神／AI24点の状態、未解決と次工程
- 新旧ワークフローの有効／無効状態
- Google Drive OAuth・実転送はユーザーの指示で最後へ延期
