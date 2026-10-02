#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


SITE_DIR = Path("_family_site")

PAGES = {
    "index.html": "prediction",
    "race_compare.html": "race_compare",
    "results.html": "results",
    "analysis.html": "analysis",
}


NAV_CSS = """
/* family-navigation-v5-unified */

.family-nav {
  display: grid !important;
  grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
  gap: 8px !important;
  width: 100% !important;
  margin: 0 0 14px 0 !important;
  padding: 6px !important;
  border: 1px solid var(--line) !important;
  border-radius: 14px !important;
  background: var(--card) !important;
  box-sizing: border-box !important;
}

.family-nav a {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  min-width: 0 !important;
  min-height: 44px !important;
  padding: 11px 5px !important;
  border: 0 !important;
  border-radius: 10px !important;
  background: transparent !important;
  color: var(--text) !important;
  text-align: center !important;
  text-decoration: none !important;
  font-size: 13px !important;
  font-weight: 800 !important;
  line-height: 1.25 !important;
  -webkit-tap-highlight-color: transparent;
}

.family-nav a:link,
.family-nav a:visited {
  color: var(--text) !important;
  text-decoration: none !important;
}

.family-nav a.active,
.family-nav a.active:link,
.family-nav a.active:visited {
  background: #2563eb !important;
  color: #ffffff !important;
  text-decoration: none !important;
}

.wrap {
  width: min(920px, 100%) !important;
  margin: 0 auto !important;
  padding: 16px 12px 48px !important;
}

header {
  margin-bottom: 12px !important;
}

header h1 {
  margin: 0 !important;
  font-size: 23px !important;
  font-weight: 800 !important;
  line-height: 1.35 !important;
  letter-spacing: 0 !important;
}

header .meta {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 4px 10px !important;
  margin-top: 6px !important;
  color: var(--muted) !important;
  font-size: 13px !important;
  line-height: 1.5 !important;
}

.notice {
  margin: 0 0 14px 0 !important;
  padding: 14px !important;
  border: 1px solid var(--line) !important;
  border-radius: 14px !important;
  background: var(--card) !important;
  color: var(--muted) !important;
  font-size: 13px !important;
  line-height: 1.7 !important;
  box-sizing: border-box !important;
}

@media (prefers-color-scheme: dark) {

  .family-nav a.active,
  .family-nav a.active:link,
  .family-nav a.active:visited {
    background: #3b82f6 !important;
    color: #ffffff !important;
  }

}

@media (max-width: 560px) {

  .family-nav {
    gap: 4px !important;
    padding: 5px !important;
  }

  .family-nav a {
    min-height: 42px !important;
    padding: 9px 2px !important;
    font-size: 11px !important;
  }

  header h1 {
    font-size: 23px !important;
  }

  header .meta {
    font-size: 13px !important;
  }

  .notice {
    padding: 13px !important;
    font-size: 13px !important;
  }

}
"""


def nav_html(
    active: str,
) -> str:

    items = [
        (
            "index.html",
            "最新予想",
            "prediction",
        ),
        (
            "race_compare.html",
            "レース照合",
            "race_compare",
        ),
        (
            "results.html",
            "結果・成績",
            "results",
        ),
        (
            "analysis.html",
            "AI分析",
            "analysis",
        ),
    ]

    links = []

    for (
        href,
        label,
        key,
    ) in items:

        active_class = (
            ' class="active"'
            if active == key
            else ""
        )

        links.append(
            f'<a href="{href}"'
            f"{active_class}>"
            f"{label}"
            "</a>"
        )

    return (
        '<nav class="family-nav">\n'
        + "\n".join(
            links
        )
        + "\n</nav>"
    )


def replace_navigation(
    text: str,
    active: str,
) -> str:

    nav = nav_html(
        active
    )

    # 既存の共通 family-nav があれば置換
    nav_pattern = re.compile(
        r'<nav\s+class=["\']family-nav["\'][^>]*>'
        r'.*?'
        r'</nav>',
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if nav_pattern.search(
        text
    ):

        return nav_pattern.sub(
            nav,
            text,
            count=1,
        )

    # race_compare.html に最初から入っている
    # class="nav" のメニューも共通UIへ置換
    old_race_nav_pattern = re.compile(
        r'<nav\s+class=["\']nav["\'][^>]*>'
        r'.*?'
        r'</nav>',
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if old_race_nav_pattern.search(
        text
    ):

        return old_race_nav_pattern.sub(
            nav,
            text,
            count=1,
        )

    if "</header>" in text:

        return text.replace(
            "</header>",
            "</header>\n\n"
            + nav,
            1,
        )

    # header がないページでは
    # h1/meta の後ろへ置ける場合を優先
    meta_match = re.search(
        r'<div\s+class=["\']meta["\'][^>]*>'
        r'.*?'
        r'</div>',
        text,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if meta_match:

        position = (
            meta_match.end()
        )

        return (
            text[:position]
            + "\n\n"
            + nav
            + text[position:]
        )

    body_match = re.search(
        r"<body[^>]*>",
        text,
        flags=re.IGNORECASE,
    )

    if not body_match:

        raise RuntimeError(
            "body/header が見つかりません"
        )

    position = (
        body_match.end()
    )

    return (
        text[:position]
        + "\n"
        + nav
        + "\n"
        + text[position:]
    )


def remove_old_nav_css(
    text: str,
) -> str:

    versions = [
        "family-navigation-v3",
        "family-navigation-v4-unified",
        "family-navigation-v5-unified",
    ]

    for version in versions:

        text = re.sub(
            rf"/\*\s*{re.escape(version)}\s*\*/"
            r".*?"
            r"(?=</style>)",
            "",
            text,
            flags=(
                re.DOTALL
                | re.IGNORECASE
            ),
        )

    return text


def inject_css(
    text: str,
) -> str:

    text = remove_old_nav_css(
        text
    )

    if "</style>" not in text:

        raise RuntimeError(
            "</style> が見つかりません"
        )

    return text.replace(
        "</style>",
        NAV_CSS
        + "\n</style>",
        1,
    )


def update_page(
    path: Path,
    active: str,
) -> None:

    if not path.exists():

        raise RuntimeError(
            f"ページがありません: {path}"
        )

    text = path.read_text(
        encoding="utf-8"
    )

    text = replace_navigation(
        text,
        active,
    )

    text = inject_css(
        text
    )

    path.write_text(
        text,
        encoding="utf-8",
    )

    print(
        "UI統一: PASS -> "
        f"{path}"
    )


def main() -> int:

    print("")
    print(
        "========================================"
    )
    print(
        "家族共有ページ 上部UI統一"
    )
    print(
        "========================================"
    )

    for (
        filename,
        active,
    ) in PAGES.items():

        update_page(
            SITE_DIR
            / filename,
            active,
        )

    print("")
    print(
        "最新予想 / レース照合 / 結果・成績 / AI分析"
    )

    print(
        "4ページ共通UI: PASS"
    )

    print(
        "========================================"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )