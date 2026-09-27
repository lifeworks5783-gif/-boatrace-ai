from urllib.request import Request, urlopen

url = (
    "https://www.boatrace.jp/owpc/pc/race/"
    "resultlist?hd=20260926&jcd=02"
)

request = Request(
    url,
    headers={
        "User-Agent": "Mozilla/5.0"
    }
)

with urlopen(request, timeout=20) as response:
    html = response.read().decode("utf-8", errors="replace")

    print("HTTPステータス:", response.status)
    print("取得文字数:", len(html))

    if "結果一覧" in html:
        print("BOAT RACE公式サイト取得成功")
    else:
        print("ページは取得できましたが、内容確認が必要です")