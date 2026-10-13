# Cloudflare独立補助取得 — 未取得レースだけ（研究版・段階1）

目的: GitHubの定期実行が遅れる場合も、Cloudflare 3分Cronが独立にD1へ保存した公式beforeinfoを利用できるようにする。

## ステージ1の役割
- `collectors/cloudflare_missing_only_bridge.py` は **研究版に直前予測がない／研究版V4から6艇の展示が取得できていない** かつ締切前28分以内のレースだけ選ぶ。
- Cloudflareの認証付き `/admin/research-beforeinfo` にそのレースIDのみ問い合わせる。最大8件ずつ。
- SHA256・公式URL・登録レースID・締切予定時刻・両取得時刻・6艇・展示タイム/ST・天候を検証する。
- 取得できたデータは `daily_inputs/YYYY/MM/DD/live/cloudflare_bridge/<時刻>/` に分離保存する。
- 未発表の場合は何も捏造せず待機。締切後のデータは締切前のライブ予測として使わない。
- **今はステージングのみ**。正本・通常予測・風神雷神・AIスコア・レース照合・公開ページは一切更新しない。

## 認証と動作条件
1. 正式版Cloudflare `ADMIN_TOKEN` を有効にしたまま、研究版のGitHub Secret `CLOUDFLARE_BACKUP_TOKEN` を同じ値で設定する。Gitリポジトリ内には置かない。
2. Cloudflare側 `feature/independent-missing-beforeinfo-export-20261013` の受入テスト・デプロイと認証APIの実確認が必要。
3. 研究版の `feature/cloudflare-missing-only-research-bridge-20261013` を受け入れた後、手動の `Cloudflare missing-only beforeinfo bridge (staging)` を実行する。
4. 保存済みV4データに重複しないこと、ステージング先のデータ件数とD1元スナップショットを照合する。
5. 上記合格後にのみ、研究版の同一計算エンジンへ橋渡しする。別のスコア計算式を作らない。

## 独立性の制約
Cloudflare側は既存の3分Cronが自走している。研究版のステージング取得は**GitHub Actionsの手動起動**であり、現段階ではCloudflareからGitHubへ自動配信されない。公開時刻や締切前予測を保証するものではない。

## 回帰検証
`python -m unittest discover -s tests -p test_cloudflare_missing_only_bridge.py`

Cloudflare認証が未設定の状態ではインポートを行わずエラー停止する。未認証の本番APIを新設しない。
