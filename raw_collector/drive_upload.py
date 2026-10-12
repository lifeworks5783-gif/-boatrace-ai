"""Idempotent private Google Drive ZIP upload with server-side checksum verification.

Requires an OAuth refresh token stored ONLY in GitHub Actions secrets. Current
ChatGPT/Drive connector authorization is NOT reusable by GitHub Actions.
Never uploads a file from the public git tree; caller supplies a local ZIP.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
FILES_ENDPOINT = "https://www.googleapis.com/drive/v3/files"
UPLOAD_ENDPOINT = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"

class DriveTransferError(RuntimeError):
    pass

def http_json(url: str, *, token: str | None = None, data: bytes | None = None,
              method: str | None = None, content_type: str | None = None,
              opener=urlopen, attempts=3, sleeper=time.sleep):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if content_type:
        headers["Content-Type"] = content_type
    request = Request(url, headers=headers, data=data, method=method)
    for n in range(attempts):
        try:
            with opener(request, timeout=30) as response:
                return json.loads(response.read(4_000_000))
        except HTTPError as ex:
            # Never echo response body (it can contain credential metadata).
            if ex.code in (429, 500, 502, 503, 504) and n < attempts - 1:
                sleeper(2 ** n)
                continue
            raise DriveTransferError(f"drive_http_status_{ex.code}") from None
        except (URLError, TimeoutError) as ex:
            if n < attempts - 1:
                sleeper(2 ** n)
                continue
            raise DriveTransferError("drive_connection_failed") from ex
    raise DriveTransferError("drive_retries_exhausted")

def access_token_from_env(*, opener=urlopen) -> str:
    names = ("GDRIVE_OAUTH_CLIENT_ID", "GDRIVE_OAUTH_CLIENT_SECRET",
             "GDRIVE_OAUTH_REFRESH_TOKEN")
    if any(not os.environ.get(n) for n in names):
        raise DriveTransferError("google_drive_oauth_not_configured")
    post = urlencode({
        "client_id": os.environ[names[0]],
        "client_secret": os.environ[names[1]],
        "refresh_token": os.environ[names[2]],
        "grant_type": "refresh_token",
    }).encode("utf-8")
    resp = http_json(TOKEN_ENDPOINT, method="POST", data=post,
        content_type="application/x-www-form-urlencoded", opener=opener)
    token = resp.get("access_token")
    if not isinstance(token,str) or not token:
        raise DriveTransferError("google_drive_token_exchange_failed")
    return token

def verify_remote_file(file_id: str, *, token: str, content: bytes, opener=urlopen):
    fields = "id,name,mimeType,size,md5Checksum,sha256Checksum,parents,trashed"
    info = http_json(FILES_ENDPOINT + "/" + file_id + "?" + urlencode({"fields":fields}),
        token=token, opener=opener)
    md5 = hashlib.md5(content).hexdigest()  # Google-calculated checksum, not as a security digest.
    sha = hashlib.sha256(content).hexdigest()
    if (info.get("trashed") or info.get("md5Checksum") != md5 or
        int(info.get("size",-1)) != len(content) or
        (info.get("sha256Checksum") and info["sha256Checksum"] != sha)):
        raise DriveTransferError("drive_server_checksum_or_size_mismatch")
    return info

def upload_private_bundle(path: Path, *, folder_id: str, token: str,
                          opener=urlopen) -> dict:
    if not folder_id or not folder_id.replace("-", "").replace("_", "").isalnum():
        raise DriveTransferError("invalid_drive_folder")
    if not path.is_file() or path.suffix.lower() != ".zip":
        raise DriveTransferError("missing_raw_bundle")
    content = path.read_bytes()
    if len(content) > 50_000_000:
        raise DriveTransferError("raw_bundle_over_50MB_split_required")
    if not content:
        raise DriveTransferError("empty_bundle")
    # First check whether this exact bundle has already been uploaded.
    # Content-addressed filenames are immutable; a mismatched copy is an error.
    q = f"'{folder_id}' in parents and name = '{path.name}' and trashed = false"
    lookup_url = FILES_ENDPOINT + "?" + urlencode({"q":q,"fields":"files(id),nextPageToken","pageSize":"3"})
    existing = http_json(lookup_url,token=token,opener=opener).get("files") or []
    for found in existing:
        fid = found.get("id")
        if fid:
            verify_remote_file(fid,token=token,content=content,opener=opener)
            return {"status":"verified_existing","name":path.name,"bytes":len(content)}
    boundary = "boatrace_raw_drive_v1_" + hashlib.sha256(content).hexdigest()[:24]
    meta = json.dumps({"name":path.name,"parents":[folder_id],
                       "mimeType":"application/zip",
                       "description":"BOAT RACE original response evidence. Private archive."},
                      separators=(",",":"),ensure_ascii=False).encode("utf-8")
    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
            + meta + f"\r\n--{boundary}\r\nContent-Type: application/zip\r\n\r\n".encode()
            + content + f"\r\n--{boundary}--\r\n".encode())
    created = http_json(UPLOAD_ENDPOINT + "&" + urlencode({"fields":"id"}),
        token=token, data=body, method="POST",
        content_type="multipart/related; boundary="+boundary,
        opener=opener)
    file_id=created.get("id")
    if not isinstance(file_id,str) or not file_id:
        raise DriveTransferError("drive_upload_no_file_id")
    verify_remote_file(file_id,token=token,content=content,opener=opener)
    return {"status":"verified_uploaded","name":path.name,"bytes":len(content)}

def main(argv=None) -> int:
    p=argparse.ArgumentParser(description="Upload exact raw ZIP to private Drive after checksum verification")
    p.add_argument("--bundle",required=True,type=Path)
    args=p.parse_args(argv)
    folder_id=os.environ.get("GDRIVE_RAW_FOLDER_ID","")
    token=access_token_from_env()
    result=upload_private_bundle(args.bundle,folder_id=folder_id,token=token)
    # No Google OAuth token, file id, raw HTML or full internal Google Drive path in logs.
    print(json.dumps(result,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
