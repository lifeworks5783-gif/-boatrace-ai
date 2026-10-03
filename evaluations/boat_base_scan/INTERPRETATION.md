# Boat base scan interpretation

## Scope
- Target dates: 2026-09-30, 2026-10-01, 2026-10-02
- Common sample: 480 completed races / 2,880 boats
- All target boats had prior-90d boat history.
- Target-day results were used only as evaluation labels; historical factors use dates before each target date.

## Factors tested
- official boat top2 rate
- prior-90d boat win rate
- prior-90d boat top2 rate
- prior-90d boat top3 rate

286 single/multi-factor weight patterns were compared with within-race rank normalization.
Primary ranking metric: unordered TOP3 exact set match.
Secondary metrics: winner match and exact 1-2-3 order.

## Leading candidate
**B-Boat1: prior-90d top2 50% + prior-90d top3 50%**

Overall (480 races):
- winner match: 16.46%
- TOP3 set match: 8.75%
- exact order: 1.67%

By date:
- 2026-09-30 (144R): winner 15.97%, TOP3 10.42%, exact 2.78%
- 2026-10-01 (168R): winner 16.67%, TOP3 7.14%, exact 1.79%
- 2026-10-02 (168R): winner 16.67%, TOP3 8.93%, exact 0.60%

## Other leading patterns
- official top2 40% + d90 top2 50% + d90 top3 10%: TOP3 8.33%
- official top2 40% + d90 top2 40% + d90 top3 20%: TOP3 8.12%
- d90 win 10% + d90 top2 40% + d90 top3 50%: TOP3 8.12%

## Interpretation / caution
The current first candidate emphasizes repeatable top2/top3 performance rather than boat win rate. It is a component candidate, not a standalone prediction model and not yet a production weight. Three target dates are insufficient for a final production conclusion. Preserve this candidate for later integration tests with racer and motor bases, then validate on additional holdout dates before adoption.
