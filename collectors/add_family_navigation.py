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


# ---------------------------------------------------------
# 3ページ共通ヘッダー・ナビゲーション
#
# 最新予想だけ旧UIに見える問題を、
# 後付けCSSで完全に統一する。
# ---------------------------------------------------------

NAV_CSS = r"""

/* family-navigation-v4-unified */

.family-nav {
  display: grid !important;

  grid-template-columns:
    repeat(
      3,
      minmax(0, 1fr)
    ) !important;

  gap: 8px !important;

  width: 100% !important;

  margin:
    0
    0
    14px
    0 !important;

  padding: 6px !important;

  border:
    1px solid
    var(--line) !important;

  border-radius:
    14px !important;

  background:
    var(--card) !important;

  box-sizing:
    border-box !important;
}


.family-nav a {
  display: flex !important;

  align-items:
    center !important;

  justify-content:
    center !important;

  min-width: 0 !important;

  min-height:
    44px !important;

  padding:
    11px
    6px !important;

  border:
    0 !important;

  border-radius:
    10px !important;

  background:
    transparent !important;

  color:
    var(--text) !important;

  text-align:
    center !important;

  text-decoration:
    none !important;

  font-size:
    14px !important;

  font-weight:
    800 !important;

  line-height:
    1.25 !important;

  -webkit-tap-highlight-color:
    transparent;
}


.family-nav a:link,
.family-nav a:visited {
  color:
    var(--text) !important;

  text-decoration:
    none !important;
}


.family-nav a.active,
.family-nav a.active:link,
.family-nav a.active:visited {
  background:
    #2563eb !important;

  color:
    #ffffff !important;

  text-decoration:
    none !important;
}


.family-nav a:active {
  transform:
    scale(0.99);
}


/* ------------------------------------------------------
   3ページでヘッダーサイズも統一
   ------------------------------------------------------ */

.wrap {
  width:
    min(
      920px,
      100%
    ) !important;

  margin:
    0
    auto !important;

  padding:
    16px
    12px
    48px !important;
}


header {
 