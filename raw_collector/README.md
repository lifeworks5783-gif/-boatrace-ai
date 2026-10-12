# 公式生データ収集の独立モジュール（検証段階）

目的：公式HTTPレスポンス本文のバイト列を、展示ST・気象・艇数などの解析前に保存する。意味の解読や予測は研究版・本番版の別処理で行う。

- 収集コード：raw_collector/archive.py（Python標準ライブラリのみ）
- 保存先：private_raw_official/YYYYMMDD/<kind>/<venue>/<race>/<SHA256>.html.gz（Git追跡除外）
- 同一HTMLは再保存せず、内容変更時は別バージョンにする。
- 元データはload_raw()で研究版が再読込可能。失敗時に偽の保存成功は返さない。
- 公式サイトはHTML等の無断転載・大量アクセスに制限があるため、原本の公開Gitへの自動pushを禁止する。
- 公開Actions標準ランナーの実行時間は無料だが、Actionsが最短5分でも遅延することと、保存やソースへのアクセスに制限があることは別。

コマンド：
  python -m raw_collector.archive --date 20261012 --out private_raw_official
  python -m raw_collector.archive --url 'https://www.boatrace.jp/owpc/pc/race/beforeinfo?hd=20261012&jcd=02&rno=3' --out private_raw_official
  python -m unittest discover -s tests -p test_raw_archiving_contract.py -v

状態：指定URLまたは公式インデックスだけの原本取得部品。全会場の自動発見・全レース収集・収集先を永続化する認証付き保管庫・定期Actionsは未実装。公開Gitに原本を掲載せず、Privateな永続保管先を接続することが先決。
独立専用リポジトリを後から作った場合、そのまま移動できる単一フォルダ構成。既存研究版や本番のロジックには触れない。
