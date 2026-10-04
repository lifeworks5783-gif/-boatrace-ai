from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


JST = timezone(timedelta(hours=9))


def parse_args():
    parser = argparse.ArgumentParser(
        description="家族共有用の予想ページを生成"
    )
    parser.add_argument(
        "--input",
        default="predictions/latest_by_deadline.json",
    )
    parser.add_argument(
        "--output-dir",
        default="_family_site",
    )
    return parser.parse_args()


def text(value):
    if value is None:
        return ""
    return str(value).strip()


def esc(value):
    return html.escape(
        text(value),
        quote=True,
    )


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def score_label(value):
    score = to_float(value)

    if score is None:
        return "未算出"

    return f"{score:.1f}"


def time_label(value):
    raw = text(value)

    if not raw:
        return "不明"

    try:
        dt = datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)

        return (
            dt.astimezone(JST)
            .strftime("%H:%M")
        )

    except ValueError:
        return raw


def updated_label(value):
    raw = text(value)

    if not raw:
        return "不明"

    try:
        dt = datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)

        return (
            dt.astimezone(JST)
            .strftime("%Y/%m/%d %H:%M")
        )

    except ValueError:
        return raw


def boat_line(boat, mark=""):
    boat_no = esc(
        boat.get("boat")
    )

    racer = esc(
        boat.get("racer_name")
    )

    score = esc(
        score_label(
            boat.get("score")
        )
    )

    name = f"{boat_no}号艇"

    if racer:
        name += f" {racer}"

    return (
        '<div class="pick">'
        f'<span class="mark">{esc(mark)}</span>'
        f'<span class="pick-name">{name}</span>'
        f'<span class="score">{score}</span>'
        "</div>"
    )


def build_card(race, index, is_completed=False):
    venue = (
        text(race.get("venue_name"))
        or text(race.get("venue_code"))
        or "会場不明"
    )

    race_no = race.get("race")

    deadline = time_label(
        race.get("deadline")
    )

    prediction_type = (
        text(
            race.get("prediction_type")
        )
        or "不明"
    )

    badge_class = (
        "live"
        if prediction_type == "直前"
        else "morning"
    )

    status_html = (
        '<div class="race-status completed">終了済み</div>'
        if is_completed
        else '<div class="race-status upcoming">締切前</div>'
    )

    boats = (
        race.get("boats")
        or []
    )

    formation = (
        race.get("formation")
        or {}
    )

    top_html = ""

    marks = [
        "◎",
        "○",
        "▲",
    ]

    for i, boat in enumerate(
        boats[:3]
    ):
        top_html += boat_line(
            boat,
            marks[i],
        )

    score_chips = []

    for boat in boats:
        score_chips.append(
            '<span class="chip">'
            f'{esc(boat.get("boat"))}号艇 '
            f'{esc(score_label(boat.get("score")))}'
            "</span>"
        )

    points = int(
        formation.get("points")
        or 0
    )

    investment = int(
        formation.get(
            "investment_100yen"
        )
        or 0
    )

    formation_type = esc(
        formation.get(
            "formation_type"
        )
        or "不明"
    )

    if points > 0:

        first = "・".join(
            esc(value)
            for value
            in formation.get(
                "first_candidates"
            )
            or []
        )

        second = "・".join(
            esc(value)
            for value
            in formation.get(
                "second_candidates"
            )
            or []
        )

        third = "・".join(
            esc(value)
            for value
            in formation.get(
                "third_candidates"
            )
            or []
        )

        combinations = " / ".join(
            esc(value)
            for value
            in formation.get(
                "combinations"
            )
            or []
        )

        formation_html = f"""
        <div class="formation">
          <div class="formation-title">
            3連単 {formation_type}・{points}点・{investment:,}円
          </div>

          <div class="formation-grid">
            <div><b>1着</b> {first or "なし"}</div>
            <div><b>2着</b> {second or "なし"}</div>
            <div><b>3着</b> {third or "なし"}</div>
          </div>

          <div class="combos">
            {combinations}
          </div>
        </div>
        """

    else:

        formation_html = """
        <div class="formation unavailable">
          フォーメーションはスコア不足のため生成なし
        </div>
        """

    return f"""
    <article class="race-card">

      <div class="race-head">

        <div class="race-order">
          {index}
        </div>

        <div class="race-main">

          <div class="deadline">
            {esc(deadline)}
          </div>

          <div class="race-name">
            {esc(venue)} {esc(race_no)}R
          </div>

        </div>

        {status_html}

        <div class="badge {badge_class}">
          {esc(prediction_type)}
        </div>

      </div>

      <div class="top-picks">
        {top_html}
      </div>

      <details>
        <summary>
          6艇すべてのスコア
        </summary>

        <div class="scores">
          {"".join(score_chips)}
        </div>
      </details>

      {formation_html}

    </article>
    """


def main():
    args = parse_args()

    input_path = Path(
        args.input
    )

    if not input_path.exists():
        raise RuntimeError(
            f"入力ファイルがありません: {input_path}"
        )

    payload = json.loads(
        input_path.read_text(
            encoding="utf-8"
        )
    )

    races = (
        payload.get("races")
        or []
    )

    updated = updated_label(
        payload.get("generated_at")
    )

    now_jst = datetime.now(JST)

    def completed(race):
        raw = text(race.get("deadline"))
        if not raw:
            return False
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=JST)
            return dt.astimezone(JST) <= now_jst
        except ValueError:
            return False

    upcoming_races = [race for race in races if not completed(race)]
    completed_races = [race for race in races if completed(race)]

    cards = "".join(
        build_card(race, index, False)
        for index, race in enumerate(upcoming_races, start=1)
    )

    all_finished = bool(races) and not upcoming_races

    if all_finished:
        cards = """
        <div class="empty all-finished">
          <div class="finished-title">本日の全レースは終了しました。</div>
          <div class="finished-copy">
            本日の最終予想は保存されています。翌日の朝、または当日の朝情報を再取得したい場合は下のボタンを押してください。
          </div>
          <button
            id="morningCollectionButton"
            class="refresh-button morning-collection-button"
            type="button"
          >
            朝のレース情報を取得
          </button>
          <div id="morningCollectionStatus" class="refresh-status">
            朝の番組表・選手・モーター情報を取得して朝予測を更新します。
          </div>
        </div>
        """

    if not cards:
        cards = """
        <div class="empty">
          現在、締切前の予測対象レースはありません。
        </div>
        """

    document = f"""<!doctype html>
<html lang="ja">

<head>

  <meta charset="utf-8">

  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >

  <meta
    name="robots"
    content="noindex,nofollow"
  >

  <meta
    http-equiv="refresh"
    content="60"
  >

  <title>
    ボートレースAI 最新予想
  </title>

  <style>

    :root {{
      color-scheme: light dark;

      --bg: #f4f6f8;
      --card: #ffffff;
      --text: #111827;
      --muted: #667085;
      --line: #e5e7eb;
      --live-bg: #dcfce7;
      --live-text: #166534;
      --morning-bg: #e0e7ff;
      --morning-text: #3730a3;
      --chip: #f3f4f6;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;

      font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        "Hiragino Sans",
        "Noto Sans JP",
        sans-serif;

      background: var(--bg);
      color: var(--text);
    }}

    .wrap {{
      width: min(920px, 100%);
      margin: 0 auto;
      padding: 16px 12px 48px;
    }}

    header {{
      position: sticky;
      top: 0;
      z-index: 10;

      margin:
        -16px
        -12px
        14px;

      padding:
        14px
        16px
        12px;

      background: var(--bg);

      border-bottom:
        1px solid
        var(--line);
    }}

    h1 {{
      margin: 0;

      font-size: 22px;
      line-height: 1.3;
    }}

    .meta {{
      margin-top: 6px;

      display: flex;
      gap: 10px;
      flex-wrap: wrap;

      color: var(--muted);

      font-size: 13px;
    }}

    .refresh-panel {{
      padding: 12px;
      margin-bottom: 12px;
      border-radius: 10px;
      background: var(--card);
      border: 1px solid var(--line);
    }}

    .refresh-button {{
      width: 100%;
      min-height: 48px;
      border: 0;
      border-radius: 10px;
      font-size: 16px;
      font-weight: 800;
      cursor: pointer;
      background: #2563eb;
      color: #ffffff;
    }}

    .refresh-button:disabled {{
      opacity: .6;
      cursor: wait;
    }}

    .refresh-status {{
      margin-top: 8px;
      min-height: 20px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }}

    .finished-title {{
      font-size: 18px;
      font-weight: 900;
      margin-bottom: 8px;
    }}

    .finished-copy {{
      margin-bottom: 14px;
      line-height: 1.6;
    }}

    .morning-collection-button {{
      margin-top: 4px;
    }}

    .notice {{
      padding: 10px 12px;
      margin-bottom: 12px;

      border-radius: 10px;

      background: var(--card);

      color: var(--muted);

      font-size: 13px;
      line-height: 1.55;
    }}

    .race-card {{
      background: var(--card);

      border:
        1px solid
        var(--line);

      border-radius: 14px;

      padding: 14px;
      margin-bottom: 12px;

      box-shadow:
        0 1px 3px
        rgba(0,0,0,.04);
    }}

    .race-head {{
      display: flex;
      align-items: center;
      gap: 10px;

      margin-bottom: 12px;
    }}

    .race-order {{
      width: 28px;
      height: 28px;

      display: grid;
      place-items: center;

      border-radius: 50%;

      background: var(--chip);

      font-weight: 700;

      flex: 0 0 auto;
    }}

    .race-main {{
      min-width: 0;
      flex: 1;
    }}

    .deadline {{
      font-size: 22px;
      font-weight: 800;
      line-height: 1.1;
    }}

    .race-name {{
      margin-top: 3px;

      font-size: 16px;
      font-weight: 700;
    }}

    .race-status {{
      flex: 0 0 auto;
      border-radius: 999px;
      padding: 5px 8px;
      font-size: 11px;
      font-weight: 800;
    }}

    .race-status.completed {{
      color: var(--muted);
      border: 1px solid var(--line);
    }}

    .race-status.upcoming {{
      display: none;
    }}

    .section-title {{
      margin: 22px 2px 10px;
      padding-top: 12px;
      border-top: 2px solid var(--line);
      font-size: 18px;
      font-weight: 900;
    }}

    .badge {{
      flex: 0 0 auto;

      border-radius: 999px;

      padding: 6px 10px;

      font-size: 13px;
      font-weight: 800;
    }}

    .badge.live {{
      background: var(--live-bg);
      color: var(--live-text);
    }}

    .badge.morning {{
      background: var(--morning-bg);
      color: var(--morning-text);
    }}

    .top-picks {{
      display: grid;
      gap: 6px;
    }}

    .pick {{
      display: grid;

      grid-template-columns:
        28px
        1fr
        auto;

      align-items: center;

      gap: 6px;

      padding: 8px 10px;

      border-radius: 10px;

      background: var(--chip);
    }}

    .mark {{
      font-size: 18px;
      font-weight: 900;
    }}

    .pick-name {{
      font-weight: 700;
      overflow-wrap: anywhere;
    }}

    .score {{
      font-weight: 800;

      font-variant-numeric:
        tabular-nums;
    }}

    details {{
      margin-top: 10px;
    }}

    summary {{
      cursor: pointer;

      font-weight: 700;

      color: var(--muted);
    }}

    .scores {{
      display: flex;
      flex-wrap: wrap;

      gap: 6px;

      margin-top: 8px;
    }}

    .chip {{
      padding: 6px 9px;

      border-radius: 999px;

      background: var(--chip);

      font-size: 13px;

      font-variant-numeric:
        tabular-nums;
    }}

    .formation {{
      margin-top: 12px;
      padding-top: 12px;

      border-top:
        1px solid
        var(--line);
    }}

    .formation-title {{
      font-weight: 800;
      margin-bottom: 8px;
    }}

    .formation-grid {{
      display: grid;
      gap: 4px;

      font-size: 14px;
    }}

    .combos {{
      margin-top: 8px;

      font-size: 13px;
      line-height: 1.6;

      overflow-wrap: anywhere;

      color: var(--muted);
    }}

    .unavailable {{
      color: var(--muted);
    }}

    .empty {{
      background: var(--card);

      border-radius: 14px;

      padding: 24px;

      text-align: center;

      color: var(--muted);
    }}

    footer {{
      margin-top: 18px;

      color: var(--muted);

      font-size: 12px;
      line-height: 1.6;
    }}

    @media (prefers-color-scheme: dark) {{

      :root {{
        --bg: #0f1115;
        --card: #171a21;
        --text: #f3f4f6;
        --muted: #a8b0bd;
        --line: #2a3039;
        --chip: #222833;

        --live-bg: #153b25;
        --live-text: #86efac;

        --morning-bg: #22285a;
        --morning-text: #c7d2fe;
      }}

    }}

  </style>

</head>

<body>

  <div class="wrap">

    <header>

      <h1>
        ボートレースAI 最新予想
      </h1>

      <div class="meta">

        <span>
          最終更新 {esc(updated)} JST
        </span>

        <span>
          締切前 {len(upcoming_races)}レース
        </span>

      </div>

    </header>

    <div class="refresh-panel" style="{'display:none;' if all_finished else ''}">
      <button
        id="refreshPredictionButton"
        class="refresh-button"
        type="button"
      >
        最新データに更新して予測
      </button>
      <div id="refreshStatus" class="refresh-status">
        押すと直前情報を再収集し、最新予測へ更新します。
      </div>
    </div>

    <div class="notice">

      最新予想には締切前レースだけを表示します。終了済みレースの予測データはPDCA・結果検証用として保存しています。

      「直前」は展示等を反映済み、
      「朝」は朝予測です。

      スコアは勝率ではなく
      比較用スコアです。

      フォーメーションは
      100円/点の検証用シミュレーションです。

    </div>

    {cards}

    <footer>

      このページは自動更新されます。

      予測は結果を保証するものではありません。

    </footer>

  </div>

  <script>
    (() => {{
      const button = document.getElementById("refreshPredictionButton");
      const status = document.getElementById("refreshStatus");
      const endpoint = "https://boatrace-family-trigger.onrender.com/trigger";

      const morningButton = document.getElementById("morningCollectionButton");
      const morningStatus = document.getElementById("morningCollectionStatus");

      if (!button || !status) return;

      if (morningButton && morningStatus) {{
        morningButton.addEventListener("click", async () => {{
          if (!window.confirm("朝のレース情報を取得して朝予測を更新します。実行しますか？")) return;
          morningButton.disabled = true;
          morningStatus.textContent = "朝情報の取得を受け付けています…";
          try {{
            const response = await fetch("https://boatrace-family-trigger.onrender.com/trigger-morning", {{
              method: "POST",
              headers: {{ "Content-Type": "application/json" }},
              body: "{{}}"
            }});
            if (response.status !== 202) throw new Error("request_failed");
            morningStatus.textContent = "朝情報の取得を開始しました。完了後にページへ反映されます。";
          }} catch (error) {{
            morningStatus.textContent = "朝情報の取得を開始できませんでした。少し時間をおいて再度お試しください。";
            morningButton.disabled = false;
          }}
        }});
      }}

      button.addEventListener("click", async () => {{
        if (!window.confirm("最新の直前情報を収集して予測を更新します。実行しますか？")) return;

        button.disabled = true;
        status.textContent = "更新を受け付けています…";

        try {{
          const response = await fetch(endpoint, {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: "{{}}"
          }});

          if (response.status !== 202) throw new Error("request_failed");

          status.textContent = "更新を開始しました。約1分後に自動で再読み込みします。";
          window.setTimeout(() => window.location.reload(), 65000);
        }} catch (error) {{
          status.textContent = "更新を開始できませんでした。少し時間をおいて再度お試しください。";
          button.disabled = false;
        }}
      }});
    }})();
  </script>

</body>

</html>
"""

    output_dir = Path(
        args.output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        output_dir
        / "index.html"
    )

    output_file.write_text(
        document,
        encoding="utf-8",
    )

    print(
        "家族共有ページ生成: PASS"
    )

    print(
        f"出力: {output_file}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )