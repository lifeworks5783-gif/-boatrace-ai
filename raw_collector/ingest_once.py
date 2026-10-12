"""One bounded run: official raw -> private Google Drive -> compact GitHub JSON.

No collection starts without a working Drive OAuth token and folder access.
Use from a trusted Actions workflow; main will commit ONLY normalized/.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
from raw_collector.archive import capture_one
from raw_collector.plan import candidate_urls
from raw_collector.drive_bundle import bundle_batch
from raw_collector.drive_upload import (
    access_token_from_env,upload_private_bundle,http_json,FILES_ENDPOINT,DriveTransferError
)
from raw_collector.normalize import normalize_verified_bundle,write_summary

JST=timezone(timedelta(hours=9))

def verify_folder(token:str,folder_id:str):
    if not folder_id or not folder_id.replace("-","").replace("_","").isalnum():
        raise DriveTransferError("drive_folder_missing")
    data=http_json(FILES_ENDPOINT+"/"+folder_id+"?fields=id,mimeType,trashed,capabilities(canAddChildren)",
                   token=token)
    if data.get("trashed") or data.get("mimeType")!="application/vnd.google-apps.folder":
        raise DriveTransferError("drive_destination_is_not_folder")
    if data.get("capabilities",{}).get("canAddChildren") is False:
        raise DriveTransferError("drive_destination_not_writable")

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--date",default=datetime.now(JST).strftime("%Y%m%d"))
    p.add_argument("--max-requests",type=int,default=12)
    p.add_argument("--repo-root",type=Path,default=Path("."))
    args=p.parse_args(argv)
    # Fail before any official requests if Drive is not configured.
    token=access_token_from_env()
    folder=os.environ.get("GDRIVE_RAW_FOLDER_ID","")
    verify_folder(token,folder)
    now=datetime.now(JST)
    planned=candidate_urls(args.repo_root,args.date,now,max_requests=args.max_requests)
    if not planned:
        print(json.dumps({"status":"no_eligible_races","date":args.date,
                          "attempted":0,"saved":0},ensure_ascii=False))
        return 0
    with tempfile.TemporaryDirectory(prefix="boatrace-raw-private-") as working:
        raw=Path(working)/"private_raw_official"
        successes=[]
        failures=[]
        for target in planned:
            result=capture_one(target["url"],raw,retries=2)
            if result["status"]=="saved":
                successes.append(result)
            else:
                failures.append({"race_id":target["race_id"],"reason":result.get("error","fetch_failed")})
        if not successes:
            raise RuntimeError("all_official_capture_attempts_failed")
        bundle,_=bundle_batch(raw,Path(working)/"out",args.date)
        verified=upload_private_bundle(bundle,folder_id=folder,token=token)
        # Never write a public summary based on a transfer that failed verification.
        normalized=normalize_verified_bundle(bundle,root=args.repo_root,
                                             transfer_status=verified["status"])
        summary=write_summary(normalized,repo_root=args.repo_root)
        outcome={"status":"archived_with_partial_failures" if failures else "archived",
                 "date":args.date,"attempted":len(planned),
                 "captured":len(successes),"failed":len(failures),
                 "drive_verified":True,"normalized_races_in_batch":len(normalized["races"]),
                 "summary":str(summary)}
        print(json.dumps(outcome,ensure_ascii=False))
        if failures:
            # Collected/verified files were already archived, but gaps are not hidden.
            return 2
        return 0

if __name__=="__main__":
    try:
        sys.exit(main())
    except Exception as ex:
        # Never log bearer tokens, refresh tokens or OAuth responses.
        print("RAW_DRIVE_PIPELINE_FAILED:"+type(ex).__name__+":"+
              str(ex)[:120],file=sys.stderr)
        sys.exit(1)
