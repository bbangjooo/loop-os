from __future__ import annotations

import json
from pathlib import Path

import pytest

import autonomy
import journal
from _canon import canonical_json, digest_bytes


def _decision(tmp_path: Path) -> Path:
    path = tmp_path / "recovery-decision.json"
    path.write_text(
        json.dumps(
            {
                "verdict": "RECOVER_AND_CONTINUE",
                "damage_assessment": "one chain link is invalid",
                "evidence_considered": "archived journal bytes and tracked anchor",
                "continuation_rationale": "readable records preserve the strongest available state",
                "accepted_uncertainty": "the damaged link cannot be independently reconstructed",
            }
        ),
        encoding="utf-8",
    )
    return path


def test_enable_records_project_local_grant(registered_project: Path) -> None:
    result = autonomy.enable(
        registered_project,
        "user invoking full-auto",
        "continue without waiting for per-incident approval",
    )
    assert result["status"] == "FULL_AUTO_ENABLED"
    assert result["journal_status"] == "RECORDED"
    grant = autonomy.load_grant(registered_project, required_scope="constitutional_jump")
    assert grant["enabled"] is True
    assert set(grant["scopes"]) == set(autonomy.GRANT_SCOPES)
    assert journal.load_events(registered_project)[-1]["kind"] == "autonomy_changed.v1"


def test_disable_is_the_rollback_path(registered_project: Path) -> None:
    autonomy.enable(registered_project, "user", "full-auto requested")
    result = autonomy.disable(registered_project, "return to governed mode")
    assert result["status"] == "FULL_AUTO_DISABLED"
    with pytest.raises(autonomy.AutonomyError, match="disabled"):
        autonomy.load_grant(registered_project)


def test_recovery_archives_original_and_rechains_readable_events(
    registered_project: Path, tmp_path: Path
) -> None:
    autonomy.enable(registered_project, "user", "recover autonomously")
    journal.write_anchor(registered_project)
    path = journal.journal_path(registered_project)
    lines = path.read_text(encoding="utf-8").splitlines()
    damaged = json.loads(lines[1])
    damaged["prev"] = "broken-link"
    lines[1] = canonical_json(damaged)
    original = ("\n".join(lines) + "\n").encode("utf-8")
    path.write_bytes(original)
    with pytest.raises(journal.JournalError, match="hash chain broken"):
        journal.load_events(registered_project)

    result = autonomy.recover(registered_project, _decision(tmp_path))

    assert result["status"] == "JOURNAL_RECOVERED"
    events = journal.load_events(registered_project)
    assert events[-1]["kind"] == "journal_recovered.v1"
    assert journal.check_anchor(registered_project)["events_since_anchor"] == 0
    archive = Path(result["archive_path"]) / "events.original.jsonl"
    assert archive.read_bytes() == original
    assert result["original_journal_digest"] == digest_bytes(original)


def test_recovery_drops_invalid_record_but_preserves_later_records(
    registered_project: Path, tmp_path: Path
) -> None:
    autonomy.enable(registered_project, "user", "recover autonomously")
    path = journal.journal_path(registered_project)
    lines = path.read_bytes().splitlines()
    path.write_bytes(lines[0] + b"\n{not-json}\n" + b"\n".join(lines[1:]) + b"\n")

    result = autonomy.recover(registered_project, _decision(tmp_path))

    assert result["dropped_records"] == 1
    state = journal.replay(registered_project)
    assert state.contract_digest is not None
    recovery = state.events[-1]["body"]
    assert recovery["dropped_records"][0]["reason"] == "invalid_json"


def test_recovery_can_create_new_genesis_when_bootstrap_is_unreadable(
    project: Path, tmp_path: Path
) -> None:
    journal.journal_path(project).parent.mkdir(parents=True)
    journal.journal_path(project).write_bytes(b"not-json\n")
    enabled = autonomy.enable(project, "user", "recover autonomously")
    assert enabled["journal_status"] == "PENDING_RECOVERY"

    result = autonomy.recover(project, _decision(tmp_path), project_id="toy-recovered")

    assert result["status"] == "JOURNAL_RECOVERED"
    state = journal.replay(project)
    assert state.project_id == "toy-recovered"
    assert state.lineage == [
        {"name": "damaged-journal", "digest": result["original_journal_digest"]}
    ]


def test_recovery_requires_a_structured_agent_decision(
    registered_project: Path, tmp_path: Path
) -> None:
    autonomy.enable(registered_project, "user", "recover autonomously")
    decision = tmp_path / "bad-decision.json"
    decision.write_text(json.dumps({"verdict": "RECOVER_AND_CONTINUE"}), encoding="utf-8")
    with pytest.raises(autonomy.AutonomyError, match="damage_assessment"):
        autonomy.recover(registered_project, decision)


def test_recovery_reuses_matching_partial_archive(
    registered_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    autonomy.enable(registered_project, "user", "recover autonomously")
    path = journal.journal_path(registered_project)
    original = path.read_bytes() + b"{broken-tail\n"
    path.write_bytes(original)
    monkeypatch.setattr(autonomy, "_stamp", lambda: "20260825T000000Z")
    recovery_dir = (
        registered_project
        / journal.JOURNAL_DIR
        / "recovery"
        / f"20260825T000000Z-{digest_bytes(original)[:12]}"
    )
    recovery_dir.mkdir(parents=True)
    (recovery_dir / "events.original.jsonl").write_bytes(original)

    result = autonomy.recover(registered_project, _decision(tmp_path))

    assert result["status"] == "JOURNAL_RECOVERED"
    assert Path(result["archive_path"]) == recovery_dir
