#!/usr/bin/env python3

from pathlib import Path


INDEX = Path(
    "_family_site/index.html"
)


NAV_HTML = """
<nav class="family-nav">

<a
  href="index.html"
  class="active"
>
  最新予想
</a>

<a href="results.html">
  結果・成績
</a>

</nav>
"""


NAV_CSS = """

.family-nav {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;

  margin-bottom: 14px;

  padding: 6px;

  border:
    1px solid
    var(--line);

  border-radius: 14px;

  background: var(--card);
}

.family-nav a {
  display: block;

  padding: 11px 8px;

  border-radius: 10px;

  text-align: center;

  text-decoration: none;

  color: var(--text);

  font-weight: 800;
}

.family-nav a.active {
  background: #2563eb;
  color: #ffffff;
}

@media (prefers-color-scheme: dark) {

  .family-nav a.active {
    background: #3b82f6;
  }

}

"""


def main() -> int:

    if not INDEX.exists():

        raise SystemExit(
            f"missing: {INDEX}"
        )

    text = INDEX.read_text(
        encoding="utf-8"
    )

    if (
        "class=\"family-nav\""
        in text
    ):

        print(
            "ナビゲーション追加済み"
        )

        return 0

    if "</style>" in text:

        text = text.replace(
            "</style>",
            NAV_CSS
            + "\n</style>",
            1,
        )

    else:

        raise SystemExit(
            "</style> not found"
        )

    if "</header>" in text:

        text = text.replace(
            "</header>",
            "</header>\n"
            + NAV_HTML,
            1,
        )

    else:

        raise SystemExit(
            "</header> not found"
        )

    INDEX.write_text(
        text,
        encoding="utf-8",
    )

    print(
        "予想ページへナビゲーション追加: PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )