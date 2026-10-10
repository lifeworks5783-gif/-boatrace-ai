"""Dispatch an existing GitHub Actions workflow and WAIT for its conclusion.

Manual refresh is a dependent sequence, not a collection of fire-and-forget
dispatches. A queued, failed or cancelled child run must never be reported
as a completed data/website refresh.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time


def gh(*args: str) -> str:
    env = os.environ.copy()
    if not (env.get("GH_TOKEN") or env.get("GITHUB_TOKEN")):
        raise RuntimeError("GH_TOKEN/GITHUB_TOKEN is required")
    p = subprocess.run(["gh", *args], check=True, text=True, capture_output=True, env=env)
    if p.stderr:
        print(p.stderr.strip(), file=sys.stderr, flush=True)
    return p.stdout.strip()


def list_run_ids(repo: str, workflow: str) -> list[int]:
    raw = gh(
        "run", "list", "--repo", repo, "--workflow", workflow,
        "--event", "workflow_dispatch", "--branch", "main",
        "--limit", "50", "--json", "databaseId",
    )
    return sorted(int(item["databaseId"]) for item in json.loads(raw or "[]"))


def wait_run(repo: str, run_id: int, deadline: float, workflow: str) -> dict:
    last = None
    while time.monotonic() < deadline:
        item = json.loads(gh("api", f"repos/{repo}/actions/runs/{run_id}"))
        status = str(item.get("status") or "")
        conclusion = str(item.get("conclusion") or "")
        label = (status, conclusion)
        if label != last:
            print(f"{workflow} run={run_id}: {status} {conclusion}", flush=True)
            last = label
        if status == "completed":
            if conclusion != "success":
                raise RuntimeError(
                    f"{workflow} run={run_id} ended {conclusion}; "
                    "downstream prediction/evaluation/publication is NOT complete"
                )
            return item
        time.sleep(8)
    raise TimeoutError(f"Timeout while awaiting {workflow} run={run_id}")


def dispatch_wait(repo: str, workflow: str, timeout: int, inputs: list[str]) -> int:
    baseline = max(list_run_ids(repo, workflow), default=0)
    cmd = ["workflow", "run", workflow, "--repo", repo, "--ref", "main"]
    for kv in inputs:
        if "=" not in kv:
            raise ValueError(f"Workflow input must be key=value, not {kv}")
        cmd += ["-f", kv]
    gh(*cmd)
    deadline = time.monotonic() + timeout
    run_id = None
    while time.monotonic() < deadline:
        ids = [x for x in list_run_ids(repo, workflow) if x > baseline]
        if ids:
            run_id = min(ids)
            break
        time.sleep(4)
    if run_id is None:
        raise TimeoutError(f"Dispatched {workflow} but no new run appeared")
    print(f"Dispatched and following {workflow} run={run_id}", flush=True)
    wait_run(repo, run_id, deadline, workflow)
    print(f"STEP_SUCCEEDED workflow={workflow} run={run_id}", flush=True)
    return run_id


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--workflow", required=True)
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    p.add_argument("--timeout-seconds", type=int, default=1000)
    p.add_argument("--input", action="append", default=[])
    a = p.parse_args()
    if not a.repo or "/" not in a.repo or not a.workflow.endswith(".yml"):
        p.error("GITHUB_REPOSITORY owner/repo and an existing .yml workflow are required")
    if a.timeout_seconds < 1:
        p.error("timeout-seconds must be positive")
    dispatch_wait(a.repo, a.workflow, a.timeout_seconds, a.input)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
