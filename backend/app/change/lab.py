"""Persistent offline lab. External reviewer commands are outside application wiring.

This simulates Git and Argo; it never claims to start a Kubernetes cluster.
"""

import argparse
import asyncio
import fcntl
import json
import os
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.adapters.git import FakeGitChangeProvider
from app.adapters.gitops import FakeGitOpsReconciler
from app.change.demo import MANIFEST, PATH, DemoVerifier, seed
from app.change.service import ChangeDispatcher, ChangeService, ChangeWatcher
from app.db.base import Base
from app.domain.change import ChangeStatus, GitOpsStatus, PullRequest
from app.repositories.change_models import ChangeRecord


def save_git(root: Path, git: FakeGitChangeProvider) -> None:
    payload = asdict(git)
    payload["pull_requests"] = {
        key: item.model_dump(mode="json") for key, item in git.pull_requests.items()
    }
    temporary = root / "git.json.tmp"
    temporary.write_text(json.dumps(payload))
    temporary.replace(root / "git.json")


def load_git(root: Path) -> FakeGitChangeProvider:
    payload = json.loads((root / "git.json").read_text())
    payload["pull_requests"] = {
        key: PullRequest.model_validate_json(json.dumps(item))
        for key, item in payload["pull_requests"].items()
    }
    return FakeGitChangeProvider(**payload)


def show(record: ChangeRecord) -> None:
    print("Synthetic offline lab; Git and Argo observations are simulated.")
    print(f"Change ID: {record.id}")
    print(f"Incident: {record.incident_id}")
    print(f"Status: {record.status.value}")
    print(f"PR: {record.pull_request_url or 'Not created'}")
    print(f"Git review: {record.review_state or 'Not observed'}")
    print(f"Source revision: {record.source_revision}")
    print(f"Merged revision: {record.merged_revision}")
    print(f"Argo revision: {record.gitops_revision}")
    print(f"Sync / Health: {record.sync_status} / {record.health_status}")
    print(f"Verification: {record.verification_status}")


async def operate(root: Path, command: str, change_id: str | None = None) -> None:
    if command in {"down", "reset"}:
        for name in ("state.db", "state.db-journal", "git.json", "git.json.tmp"):
            (root / name).unlink(missing_ok=True)
        print("Synthetic lab state removed; no external repository or cluster was changed.")
        return
    if command != "up" and not (root / "git.json").exists():
        raise ValueError("Lab is not initialized. Run make gitops-lab-up first.")
    engine = create_engine(f"sqlite:///{root / 'state.db'}")
    try:
        Base.metadata.create_all(engine)
        with Session(engine, expire_on_commit=False) as db:
            record = db.scalar(select(ChangeRecord))
            if record is None:
                if command != "up":
                    raise ValueError("Lab state is incomplete; reset and initialize again")
                intent, profile = seed(db)
                git = FakeGitChangeProvider(base_files={PATH: MANIFEST})
                save_git(root, git)
                service = ChangeService(db, git=git)
                record = service.propose(intent, profile)
                await service.prepare(record.id)
            else:
                git = load_git(root)
                service = ChangeService(db, git=git)
            if change_id is not None and change_id != record.id:
                raise ValueError("CHANGE_ID does not match this synthetic lab")
            if command in {"approve", "review", "merge", "reconcile"} and not change_id:
                raise ValueError("CHANGE_ID is required; obtain it from make gitops-lab-status")
            if command == "approve":
                preview = service.preview(record)
                if preview is None:
                    raise ValueError("No reviewed semantic preview")
                await service.approve(
                    record.id,
                    actor="external-lab-operator",
                    reason="Reviewed synthetic rollback preview",
                    expected_plan=preview.plan_fingerprint,
                )
                await ChangeDispatcher(db, git=git).dispatch_one(change_id=record.id)
                save_git(root, git)
            elif command in {"review", "merge"}:
                if not record.pull_request_id or record.status not in {
                    ChangeStatus.WAITING_REVIEW,
                    ChangeStatus.APPROVED_FOR_MERGE,
                }:
                    raise ValueError("Lab change must have an open PR awaiting external review")
                if command == "review":
                    git.external_review(record.pull_request_id, approved=True)
                else:
                    git.external_merge(record.pull_request_id)
                save_git(root, git)
                print(f"External synthetic reviewer action persisted: {command}")
                print("Run make gitops-reconcile to observe the external result.")
            elif command == "reconcile":
                if not record.pull_request_id:
                    raise ValueError("PR creation must precede reconciliation")
                reconciler = FakeGitOpsReconciler(
                    GitOpsStatus(
                        application_ref="demo-api",
                        revision=git.base_revision,
                        sync_status="Synced",
                        health_status="Healthy",
                    )
                )
                await ChangeWatcher(db, git=git, gitops=reconciler, verifier=DemoVerifier()).poll(
                    record.id
                )
            show(record)
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("up", "status", "approve", "review", "merge", "reconcile", "reset", "down"),
    )
    parser.add_argument("--change-id")
    args = parser.parse_args()
    root = Path(os.environ.get("OPSPILOT_GITOPS_LAB_STATE", ".cache/gitops-lab")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    # Serialize independent CLI processes. Status never advances the workflow.
    with (root / "lab.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            asyncio.run(operate(root, args.command, args.change_id))
        except ValueError as exc:
            parser.exit(1, f"GitOps lab: {exc}\n")


if __name__ == "__main__":
    main()
