#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


SITE_DIR = Path(
    "_family_site"
)

PAGES = {
    "index.html":
        "prediction",

    "results.html":
        "results",

    "analysis.html":
        "analysis",
}


NAV_CSS = """

/* family-navigation-v3 */

.family-nav {
  grid-template-columns:
    repeat(
      3,
      minmax(0, 1fr)
    ) !important;
}

.family-nav a {
  min-width: 0;
}

@media (max-width: 560px) {

  .family-nav a {
    font-size: 12px;

    padding-left: 4px;
    padding-right: 4px;
  }

}

"""


def nav_html(
    active: str,
) -> str:

    def link(
        href: str,
        label: str,
        key: str,
    ) -> str:

        active_class = (
            ' class="active"'
            if active == key
            else ""
        )

        return (
            f'<a href="{href}"'
            f"{active_class}>"
            f"{label}"
            "</a>"
        )

    return (
        '<nav class="family-nav">\n'
        + link(
            "index.html",
            "最新予想",
            "prediction",
        )
        + "\n"
        + link(
            "results.html",
            "結果・成績",
            "results",
        )
        + "\n"
        + link(
            "analysis.html",
            "AI分析",
            "analysis",
        )
        + "\n</nav>"
    )


def update_page(
    path: Path,
    active: str,
) -> None:

    if not path.exists():

        raise SystemExit(
            f"missing: {path}"
        )

    text = path.read_text(
        encoding="utf-8"
    )

    nav = nav_html(
        active
    )

    nav_pattern = re.compile(
        r'<nav\s+class=["\']family-nav["\'][^>]*>.*?</nav>',
        re.IGNORECASE
        | re.DOTALL,
    )

    if nav_pattern.search(
        text
    ):

        text = (
            nav_pattern.sub(
                nav,
                text,
                count=1,
            )
        )

    elif "</header>" in text:

        text = text.replace(
            "</header>",
            "</header>\n"
            + nav,
            1,
        )

    else:

        body_match = re.search(
            r"<body[^>]*>",
            text,
            flags=re.IGNORECASE,
        )

        if not body_match:

            raise SystemExit(
                "body/header not found: "
                f"{path}"
            )

        insert_at = (
            body_match.end()
        )

        text = (
            text[:insert_at]
            + "\n"
            + nav
            + text[insert_at:]
        )

    if (
        "family-navigation-v3"
        not in text
    ):

        if "</style>" in text:

            text = text.replace(
                "</style>",
                NAV_CSS
                + "\n</style>",
                1,
            )

        else:

            raise SystemExit(
                "style block not found: "
                f"{path}"
            )

    path.write_text(
        text,
        encoding="utf-8",
    )

    print(
        "3タブナビ更新: PASS -> "
        f"{path}"
    )


def main() -> int:

    for (
        filename,
        active,
    ) in PAGES.items():

        update_page(
            SITE_DIR
            / filename,
            active,
        )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )