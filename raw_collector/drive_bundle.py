"""Bundle immutable original responses; never publish verbatim HTML into public Git.

Builds one ZIP per collection batch containing original gzip bodies, provenance
JSON and a manifest with the source SHA256. Exact bytes are recoverable.
"""
from __future__ import annotations
import hashlib
import json
import re
import tempfile
import zipfile
from pathlib import Path
from raw_collector.archive import load_raw, source_identity

SCHEMA = "boatrace-drive-raw-v1"

def bundle_batch(raw_dir: Path, output_dir: Path, day: str) -> tuple[Path, dict]:
    if not re.fullmatch(r"\d{8}", day):
        raise ValueError("invalid_date")
    source = raw_dir / day
    if not source.is_dir():
        raise FileNotFoundError("no_raw_snapshots")
    gz_paths = sorted(source.rglob("*.html.gz"))
    if not gz_paths or len(gz_paths) > 500:
        raise ValueError("empty_or_oversized_bundle")
    manifest = {"format": SCHEMA, "date": day, "entries": []}
    for file in gz_paths:
        meta_file = file.with_name(file.name.replace(".html.gz", ".json"))
        if not meta_file.is_file():
            raise ValueError("raw_metadata_missing")
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        raw = load_raw(file)
        digest = hashlib.sha256(raw).hexdigest()
        if meta.get("sha256") != digest or int(meta.get("byte_count", -1)) != len(raw):
            raise ValueError("raw_metadata_mismatch")
        date, kind, venue, race = source_identity(meta.get("url", ""))
        expected = Path(day) / kind / venue / race / (digest + ".html.gz")
        if date != day or file.relative_to(raw_dir) != expected:
            raise ValueError("raw_path_identity_mismatch")
        manifest["entries"].append({
            "path": str(file.relative_to(raw_dir)).replace("\\", "/"),
            "sha256": digest, "bytes": len(raw),
            "source_url": meta["url"], "requested_at": meta.get("requested_at"),
            "received_at": meta.get("received_at")
        })
    output_dir.mkdir(parents=True, exist_ok=True)
    # Unique, content-addressed bundle, deterministic given the same snapshots.
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")) + "\n").encode("utf-8")
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    dest = output_dir / f"boatrace_raw_{day}_{manifest_hash[:20]}.zip"
    if dest.exists():
        with zipfile.ZipFile(dest) as zf:
            if zf.read("manifest.json") != manifest_bytes:
                raise ValueError("existing_bundle_manifest_mismatch")
        return dest, manifest
    with tempfile.NamedTemporaryFile(prefix=".boatrace-drive-",suffix=".tmp",
                                     dir=output_dir,delete=False) as fp:
        tmp = Path(fp.name)
    try:
        with zipfile.ZipFile(tmp,mode="w",compression=zipfile.ZIP_STORED) as zf:
            zf.writestr("manifest.json", manifest_bytes)
            for file in gz_paths:
                rel = file.relative_to(raw_dir).as_posix()
                zf.write(file, rel)
                meta_file = file.with_name(file.name.replace(".html.gz",".json"))
                zf.write(meta_file, meta_file.relative_to(raw_dir).as_posix())
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)
    return dest, manifest

def validate_bundle(bundle: Path) -> dict:
    with zipfile.ZipFile(bundle) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        if manifest.get("format") != SCHEMA or not manifest.get("entries"):
            raise ValueError("bundle_manifest_invalid")
        for entry in manifest["entries"]:
            stored = zf.read(entry["path"])
            # Recompute raw SHA256 instead of trusting metadata or the ZIP checksum.
            import gzip
            body = gzip.decompress(stored)
            if hashlib.sha256(body).hexdigest() != entry["sha256"] or len(body) != entry["bytes"]:
                raise ValueError("bundle_raw_checksum_mismatch")
        return manifest
