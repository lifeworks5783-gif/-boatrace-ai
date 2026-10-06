"""Family/public site shared visual theme.
Edit THEME_CSS here to change the color atmosphere of all public pages.
"""

THEME_CSS = r"""
:root {
  color-scheme: light dark;
  --bg: #bfd2e1;
  --surface: #e8f1f6;
  --card: #eaf2f7;
  --card-strong: #f3f7fa;
  --panel: #d8e6ef;
  --score-row: #cfdfeb;
  --chip: #d8e6ef;
  --text: #172033;
  --muted: #60758a;
  --line: #aec4d4;
  --primary: #174f7a;
  --primary-strong: #123d60;
  --primary-soft: #d2e3ef;
  --action: #167c68;
  --action-strong: #116353;
  --analysis-action: #704286;
  --live-bg: #cceae3;
  --live-text: #0e6659;
  --live-accent: #168477;
  --morning-bg: #d4e5f6;
  --morning-text: #285a91;
  --morning-accent: #3976b8;
  --good-bg: #dcefe6;
  --good-text: #17603f;
  --warn-bg: #f5e5cf;
  --warn-text: #8a5317;
  --warning: #a94646;
}
body { background: var(--bg) !important; color: var(--text) !important; }
.family-nav, .nav { background: var(--surface) !important; border-color: var(--line) !important; }
.family-nav a.active, .family-nav a.active:link, .family-nav a.active:visited,
.nav a.active, .nav a.active:link, .nav a.active:visited {
  background: var(--primary) !important; color:#fff !important;
}
.notice, .note, .race-card, .card, .metric-card, .summary-card, .summary-box, .panel, .section, .analysis-section {
  background: var(--card) !important;
  border-color: var(--line) !important;
}
.pick, .chip, .result-box, .bet-box, .metric, .stat, .score-row, .actual, .tag, .score-chip, .simulation-box, .money-box, .ai-result-pick {
  background: var(--score-row) !important;
}


/* Race comparison and legacy page aliases: keep all surfaces on the shared theme. */
.summary-box, .race-card, .empty { background: var(--card) !important; border-color: var(--line) !important; }
.actual, .tag, .score-chip, .simulation-box, .money-box, .ai-result-pick {
  background: var(--score-row) !important;
}
"""