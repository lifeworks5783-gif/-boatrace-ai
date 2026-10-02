from collections import defaultdict

def build_venue_course_features(history, as_of_date, summarize, rows_in_days, prefixed, trend_fields, latest_venue_name):
    """競艇場×実進入コース別の30日・90日特徴量を生成する。"""
    groups = defaultdict(list)
    for row in history:
        course = row.get("course")
        if course not in {1, 2, 3, 4, 5, 6}:
            continue
        groups[(row["venue_code"], course)].append(row)

    output = []
    for venue_code, course in sorted(groups):
        rows = groups[(venue_code, course)]
        d30 = summarize(rows_in_days(rows, as_of_date, 30))
        d90 = summarize(rows_in_days(rows, as_of_date, 90))
        output.append({
            "as_of_date": as_of_date.strftime("%Y%m%d"),
            "venue_code": venue_code,
            "venue_name": latest_venue_name(rows),
            "course": course,
            "history_first_date": rows[0]["date_text"],
            "history_last_date": rows[-1]["date_text"],
            "history_starts": len(rows),
            **prefixed("d30", d30),
            **prefixed("d90", d90),
            **trend_fields(d30, d90),
        })
    return output
