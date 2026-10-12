"""Parser-independent capture of official HTTP response bytes.

No ST, six-boat, weather, result, or AI validation belongs in acquisition.
Official verbatim HTML must not be pushed to a public Git repository.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

JST = timezone(timedelta(hours=9))
ALLOWED = {"/owpc/pc/race/index", "/owpc/pc/race/racelist", "/owpc/pc/race/beforeinfo"}
MAX_BYTES = 1_500_000

def source_identity(url: str) -> tuple[str, str, str, str]:
    u = urlsplit(url)
    if u.scheme != "https" or u.hostname != "www.boatrace.jp" or u.path not in ALLOWED:
        raise ValueError("untrusted_official_url")
    p = parse_qs(u.query)
    day = (p.get("hd") or [""])[0]
    if not re.fullmatch(r"\d{8}", day):
        raise ValueError("invalid_official_date")
    kind = u.path.rsplit("/", 1)[1]
    if kind == "index":
        return day, kind, "00", "00"
    venue = (p.get("jcd") or [""])[0]
    race = (p.get("rno") or [""])[0]
    if not re.fullmatch(r"\d{2}", venue) or not race.isdigit() or not 1 <= int(race) <= 12:
        raise ValueError("invalid_race_identity")
    return day, kind, venue, f"{int(race):02d}"

def source_url(day: str, kind: str, venue: str = "00", race: int = 0) -> str:
    if kind not in {"index", "racelist", "beforeinfo"}:
        raise ValueError("invalid_source_kind")
    params = {"hd": day}
    if kind != "index":
        params.update(jcd=venue, rno=str(race))
    url = f"https://www.boatrace.jp/owpc/pc/race/{kind}?{urlencode(params)}"
    source_identity(url)
    return url

def record_response(root: Path, *, url: str, payload: bytes, requested_at: str,
                    received_at: str, status: int = 200, content_type: str = "text/html") -> dict:
    day, kind, venue, race = source_identity(url)
    if status != 200 or not payload or len(payload) > MAX_BYTES:
        raise ValueError("invalid_raw_response")
    sha = hashlib.sha256(payload).hexdigest()
    base = root / day / kind / venue / race
    base.mkdir(parents=True, exist_ok=True)
    name = base / f"{sha}.html.gz"
    meta = base / f"{sha}.json"
    if not name.exists():
        with tempfile.NamedTemporaryFile(dir=base, prefix=".raw-", suffix=".tmp", delete=False) as fp:
            tmp = Path(fp.name)
            try:
                with gzip.GzipFile(filename="", mode="wb", fileobj=fp, mtime=0) as gz:
                    gz.write(payload)
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
        os.replace(tmp, name)
    if not meta.exists():
        meta.write_text(json.dumps({"format": "boatrace-raw-v1", "url": url,
            "sha256": sha, "requested_at": requested_at, "received_at": received_at,
            "status": status, "content_type": content_type, "byte_count": len(payload)},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "saved", "url": url, "sha256": sha, "path": str(name), "bytes": len(payload)}

def load_raw(path: Path) -> bytes:
    with gzip.open(path, "rb") as fp:
        payload = fp.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES or hashlib.sha256(payload).hexdigest() != path.stem.replace(".html", ""):
        raise ValueError("raw_checksum_mismatch")
    return payload

def capture_one(url: str, root: Path, *, opener=urlopen, timeout: float=12,
                retries: int=2, pause=time.sleep) -> dict:
    source_identity(url)
    failure = ""
    for n in range(retries + 1):
        requested_at = datetime.now(JST).isoformat()
        try:
            request = Request(url, headers={"User-Agent": "BoatRaceResearchRawCollector/1.0",
                                            "Accept": "text/html"})
            with opener(request, timeout=timeout) as response:
                status = response.getcode()
                payload = response.read(MAX_BYTES + 1)
                content_type = response.headers.get("Content-Type", "text/html")
            return record_response(root, url=url, payload=payload, requested_at=requested_at,
                received_at=datetime.now(JST).isoformat(), status=status,
                content_type=content_type)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            failure = str(exc)[:180]
            if n < retries:
                pause(1.5 * (n + 1))
    return {"status": "failed", "url": url, "error": failure}

def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=datetime.now(JST).strftime("%Y%m%d"))
    p.add_argument("--url", action="append", default=[])
    p.add_argument("--out", default="private_raw_official")
    p.add_argument("--max-requests", type=int, default=15)
    opts = p.parse_args(argv)
    if not re.fullmatch(r"\d{8}", opts.date) or not 1 <= opts.max_requests <= 50:
        p.error("invalid date or max-requests")
    urls = opts.url or [source_url(opts.date, "index")]
    results = []
    for url in dict.fromkeys(urls):
        if len(results) >= opts.max_requests:
            break
        try:
            results.append(capture_one(url, Path(opts.out)))
        except ValueError as exc:
            results.append({"status": "failed", "url": url, "error": str(exc)})
    print(json.dumps({"count": len(results), "saved": sum(x["status"] == "saved" for x in results),
                      "failed": sum(x["status"] == "failed" for x in results)}, ensure_ascii=False))
    return int(any(x["status"] == "failed" for x in results))

if __name__ == "__main__":
    sys.exit(main())
