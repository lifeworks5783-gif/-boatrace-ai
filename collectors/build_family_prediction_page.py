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


def score_delta_html(boat, morning_score_map):
    if not morning_score_map:
        return ""
    key = text(boat.get("boat"))
    try:
        live = float(boat.get("score"))
        morning = float(morning_score_map.get(key))
    except (TypeError, ValueError):
        return ""
    delta = live - morning
    if abs(delta) < 0.05:
        return '<span class="score-delta flat">→ ±0.0</span>'
    if delta > 0:
        return f'<span class="score-delta up">▲ +{delta:.1f}</span>'
    return f'<span class="score-delta down">▼ {delta:.1f}</span>'


def boat_line(boat, mark="", morning_score_map=None):
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
        f'{score_delta_html(boat, morning_score_map)}'
        "</div>"
    )


def _prediction_body(boats, formation, label, morning_score_map=None):
    top_html = "".join(boat_line(boat, ["◎","○","▲"][i], morning_score_map) for i, boat in enumerate(boats[:3]))
    chips = "".join('<span class="chip">'+esc(boat.get("boat"))+'号艇 '+esc(score_label(boat.get("score")))+'</span>' for boat in boats)
    points = int(formation.get("points") or 0)
    if points:
        ftype=esc(formation.get("formation_type") or "不明")
        first="・".join(esc(v) for v in formation.get("first_candidates") or [])
        second="・".join(esc(v) for v in formation.get("second_candidates") or [])
        third="・".join(esc(v) for v in formation.get("third_candidates") or [])
        combos=" / ".join(esc(v) for v in formation.get("combinations") or [])
        inv=int(formation.get("investment_100yen") or 0)
        form=f'<div class="formation"><div class="formation-title">3連単 {ftype}・{points}点・{inv:,}円</div><div class="formation-grid"><div><b>1着</b> {first or "なし"}</div><div><b>2着</b> {second or "なし"}</div><div><b>3着</b> {third or "なし"}</div></div><div class="combos">{combos}</div></div>'
    else:
        form='<div class="formation unavailable">フォーメーションはスコア不足のため生成なし</div>'
    return f'<div class="race-prediction-view" data-view="{esc(label)}"><div class="top-picks">{top_html}</div><details><summary>6艇すべてのスコア</summary><div class="scores">{chips}</div></details>{form}</div>'


def build_card(race, index, is_completed=False):
    venue=text(race.get("venue_name")) or text(race.get("venue_code")) or "会場不明"
    prediction_type=text(race.get("prediction_type")) or "不明"
    badge_class="live" if prediction_type=="直前" else "morning"
    status_html='<div class="race-status completed">終了済み</div>' if is_completed else '<div class="race-status upcoming">締切前</div>'
    boats=race.get("boats") or []; formation=race.get("formation") or {}
    morning_boats=race.get("morning_boats") or []; morning_formation=race.get("morning_formation") or {}
    has_switch=prediction_type=="直前" and len(morning_boats)==6
    morning_score_map = {text(x.get("boat")): x.get("score") for x in morning_boats}
    current=_prediction_body(boats,formation,prediction_type,morning_score_map if has_switch else None)
    switch=""
    morning=""
    if has_switch:
        switch='<div class="race-view-tabs"><button type="button" class="race-view-tab" data-race-view="朝">朝予想</button><button type="button" class="race-view-tab active" data-race-view="直前">直前予想</button></div>'
        morning=_prediction_body(morning_boats,morning_formation,"朝").replace('class="race-prediction-view"','class="race-prediction-view hidden"')
    return f"""
    <article class="race-card">
      <div class="race-head">
        <div class="race-order">{index}</div>
        <div class="race-main"><div class="deadline">{esc(time_label(race.get("deadline")))}</div><div class="race-name">{esc(venue)} {esc(race.get("race"))}R</div></div>
        {status_html}
        <div class="badge {badge_class}">{esc(prediction_type)}</div>
      </div>
      {switch}
      {morning}
      {current}
    </article>
    """


def build_ai_card(race, index):
    venue = text(race.get("venue_name")) or text(race.get("venue_code")) or "会場不明"
    deadline = time_label(race.get("deadline"))
    ai = race.get("ai_score_prediction") or {}
    position = ai.get("position_scores") or []
    combos = (ai.get("all_120_combinations") or [])[:12]
    if not combos:
        combos = ai.get("combinations") or []
    points = int(ai.get("points") or 0)
    score_rows = "".join(
        '<tr>'
        f'<td>{esc(x.get("boat"))}号艇</td>'
        f'<td>{esc(score_label(x.get("first_score")))}</td>'
        f'<td>{esc(score_label(x.get("second_score")))}</td>'
        f'<td>{esc(score_label(x.get("third_score")))}</td>'
        '</tr>'
        for x in position
    )
    combo_rows = "".join(
        '<div class="ai-combo">'
        f'<b>{i}位 {esc(x.get("combination"))}</b>'
        f'<span>AI評価 {esc(score_label(x.get("score")))}点</span>'
        '</div>'
        for i, x in enumerate(combos, 1)
    )
    return f"""
    <article class="race-card">
      <div class="race-head">
        <div class="race-order">{index}</div>
        <div class="race-main">
          <div class="deadline">{esc(deadline)}</div>
          <div class="race-name">{esc(venue)} {esc(race.get("race"))}R</div>
        </div>
        <div class="badge live">AIスコア</div>
      </div>
      <div class="formation-title">AIスコア予測・上位12点</div>\n      <div class="ai-note">AI独自スコアによる組み合わせ評価</div>
      <div class="ai-candidates">
        <div><b>1着候補</b> {"・".join(esc(x) for x in ai.get("first_candidates") or [])}</div>
        <div><b>2着候補</b> {"・".join(esc(x) for x in ai.get("second_candidates") or [])}</div>
        <div><b>3着候補</b> {"・".join(esc(x) for x in ai.get("third_candidates") or [])}</div>
      </div>
      <div class="ai-combos">{combo_rows or "AI予測はまだ生成されていません。"}</div>
      <details>
        <summary>着順別AIスコアを見る</summary>
        <div class="ai-table-wrap">
          <table class="ai-table">
            <thead><tr><th>艇</th><th>1着</th><th>2着</th><th>3着</th></tr></thead>
            <tbody>{score_rows}</tbody>
          </table>
        </div>
      </details>
      <div class="ai-note">予想はAI順位上位12点まで表示。収支検証は上位8点を各100円、1レース800円として集計します。</div>
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
    ai_cards = "".join(
        build_ai_card(race, index)
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

      --bg: #cddce8;\n      --action: #167c68;\n      --action-strong: #116353;
      --card: #f4f8fb;\n      --panel: #e8f1f6;\n      --score-row: #dce8f0;
      --text: #172033;
      --muted: #64748b;
      --line: #c4d4e0;
      --primary: #174f7a;
      --primary-strong: #163b5c;
      --primary-soft: #dceaf5;
      --live-bg: #d5f0e9;
      --live-text: #11675b;
      --live-accent: #168477;
      --morning-bg: #dceafb;
      --morning-text: #285a91;
      --morning-accent: #3976b8;
      --chip: #dfeaf1;
      --warning: #b54747;
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
      background: var(--action);
      color: #f4f8fb;
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

    .prediction-tabs {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      margin-bottom: 10px;
    }}
    .prediction-tab {{
      min-height: 44px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--card);
      color: var(--text);
      font-weight: 800;
      cursor: pointer;
    }}
    .prediction-tab.active {{
      background: var(--primary);
      color: #fff;
      border-color: var(--primary);
    }}
    .prediction-panel {{ display: none; }}\n    .race-view-tabs {{ display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px; }}\n    .race-view-tab {{ min-height:38px;border:1px solid var(--line);border-radius:9px;background:var(--card);color:var(--text);font-weight:800;cursor:pointer; }}\n    .race-view-tab[data-race-view="朝"].active {{ background:var(--morning-accent);color:#fff;border-color:var(--morning-accent); }}\n    .race-view-tab[data-race-view="直前"].active {{ background:var(--live-accent);color:#fff;border-color:var(--live-accent); }}\n    .race-prediction-view.hidden {{ display:none; }}\n    .score-delta {{ margin-left:8px;font-size:13px;font-weight:900;white-space:nowrap; }}\n    .score-delta.up {{ color:#a33f58; }}\n    .score-delta.down {{ color:#2f6690; }}\n    .score-delta.flat {{ color:var(--muted); }}
    .prediction-panel.active {{ display: block; }}
    .ai-candidates {{
      display: grid;
      gap: 5px;
      margin: 8px 0 12px;
      font-size: 14px;
    }}
    .ai-combos {{ display: grid; gap: 6px; }}
    .ai-combo {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      padding: 8px 10px;
      border-radius: 9px;
      background: var(--score-row);
    }}
    .ai-table-wrap {{ overflow-x: auto; margin-top: 8px; }}
    .ai-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .ai-table th, .ai-table td {{ padding: 7px; border-bottom: 1px solid var(--line); text-align: right; }}
    .ai-table th:first-child, .ai-table td:first-child {{ text-align: left; }}
    .ai-note {{ margin-top: 10px; color: var(--muted); font-size: 12px; }}

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

      background: var(--score-row);

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

      background: var(--score-row);
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

      background: var(--score-row);

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
        --bg: #0d1520;
        --card: #141f2c;
        --text: #eef4f8;
        --muted: #9eafbf;
        --line: #293949;
        --primary: #4f91c7;
        --primary-strong: #75add8;
        --primary-soft: #172c3f;
        --chip: #1b2a38;
        --live-bg: #153b38;
        --live-text: #83d7c9;
        --live-accent: #278f83;
        --morning-bg: #1d3551;
        --morning-text: #a9cbed;
        --morning-accent: #477fb5;
        --warning: #e58a8a;
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

    <div class="prediction-tabs">
      <button class="prediction-tab active" data-tab="normal" type="button">通常予測</button>
      <button class="prediction-tab" data-tab="ai" type="button">AIスコア予測</button>
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

    <div id="normalPredictionPanel" class="prediction-panel active">
      {cards}
    </div>
    <div id="aiPredictionPanel" class="prediction-panel">
      {ai_cards}
    </div>

    <footer>

      このページは自動更新されます。

      予測は結果を保証するものではありません。

    </footer>

  </div>

  <script>
    (() => {{
      const tabs = document.querySelectorAll(".prediction-tab");
      const normalPanel = document.getElementById("normalPredictionPanel");
      const aiPanel = document.getElementById("aiPredictionPanel");
      tabs.forEach(tab => tab.addEventListener("click", () => {{
        const ai = tab.dataset.tab === "ai";
        tabs.forEach(x => x.classList.toggle("active", x === tab));
        if (normalPanel) normalPanel.classList.toggle("active", !ai);
        if (aiPanel) aiPanel.classList.toggle("active", ai);
      }}));

      document.querySelectorAll(".race-card").forEach(card => {{
        const viewTabs = card.querySelectorAll(".race-view-tab");
        viewTabs.forEach(viewTab => viewTab.addEventListener("click", () => {{
          const wanted = viewTab.dataset.raceView;
          viewTabs.forEach(x => x.classList.toggle("active", x === viewTab));
          card.querySelectorAll(".race-prediction-view").forEach(panel => panel.classList.toggle("hidden", panel.dataset.view !== wanted));
          const badge = card.querySelector(".badge");
          if (badge) {{
            badge.textContent = wanted;
            badge.classList.toggle("live", wanted === "直前");
            badge.classList.toggle("morning", wanted === "朝");
          }}
        }}));
      }});

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
# shared-theme-publish-trigger-v1

# execution-pink-theme-refresh-v1

# execution-pink-theme-refresh-v2

# inverted-theme-refresh-v1

# softer-execution-rose-refresh-v1

# score-delta-publish-v1

# score-delta-publish-v2
