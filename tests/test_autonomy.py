from __future__ import annotations

import json
import tomllib
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
    assert Path(result["config_path"]) == autonomy.config_path(registered_project)
    parsed = tomllib.loads(autonomy.config_path(registered_project).read_text(encoding="utf-8"))
    assert parsed["schema"] == autonomy.CONFIG_SCHEMA
    assert parsed["autonomy"]["mode"] == "full_auto"
    assert parsed["autonomy"]["constitutional_jumps"] == "agent"
    assert parsed["autonomy"]["journal_recovery"] == "agent"
    assert parsed["autonomy"]["continue_until"] == "external_goal"
    grant = autonomy.load_grant(registered_project, required_scope="constitutional_jump")
    assert grant["enabled"] is True
    assert set(grant["scopes"]) == set(autonomy.GRANT_SCOPES)
    assert journal.load_events(registered_project)[-1]["kind"] == "autonomy_changed.v1"


def test_disable_is_the_rollback_path(registered_project: Path) -> None:
    autonomy.enable(registered_project, "user", "full-auto requested")
    result = autonomy.disable(registered_project, "return to governed mode")
    assert result["status"] == "FULL_AUTO_DISABLED"
    parsed = tomllib.loads(autonomy.config_path(registered_project).read_text(encoding="utf-8"))
    assert parsed["autonomy"]["mode"] == "governed"
    assert parsed["autonomy"]["constitutional_jumps"] == "human"
    with pytest.raises(autonomy.AutonomyError, match="disabled"):
        autonomy.load_grant(registered_project)


def _legacy_grant(project: Path, *, enabled: bool = True) -> Path:
    path = autonomy.legacy_grant_path(project)
    path.write_text(
        json.dumps(
            {
                "schema": autonomy.LEGACY_GRANT_SCHEMA,
                "enabled": enabled,
                "approved_by": "legacy user",
                "statement": "delegate old full-auto mode",
                "scopes": list(autonomy.GRANT_SCOPES),
                "granted_at": "2026-08-25T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_legacy_grant_remains_readable_during_migration_window(project: Path) -> None:
    legacy = _legacy_grant(project)
    grant = autonomy.load_grant(project, required_scope="journal_recovery")
    assert grant["source"] == "legacy"
    assert autonomy.grant_path(project) == legacy
    assert autonomy.status(project)["migration_required"] is True


def test_migrate_expands_config_and_retires_legacy_grant(
    registered_project: Path,
) -> None:
    legacy = _legacy_grant(registered_project)
    original_digest = digest_bytes(legacy.read_bytes())

    result = autonomy.migrate(registered_project)

    assert result["status"] == "CONFIG_MIGRATED"
    assert autonomy.load_grant(registered_project)["source"] == "config"
    retired = json.loads(legacy.read_text(encoding="utf-8"))
    assert retired["enabled"] is False
    assert retired["migrated_to"] == ".loop-os/config.toml"
    migration_event = journal.load_events(registered_project)[-1]["body"]
    assert migration_event["legacy_grant_original_digest"] == original_digest
    assert migration_event["legacy_grant_retired_digest"] == digest_bytes(legacy.read_bytes())
    assert autonomy.migrate(registered_project)["status"] == "ALREADY_MIGRATED"


def test_missing_config_defaults_to_governed_status(project: Path) -> None:
    result = autonomy.status(project)
    assert result["status"] == "FULL_AUTO_DISABLED"
    assert result["mode"] == "governed"
    assert result["reason"] == "Loop OS config absent"
    assert result["migration_required"] is False


def test_hand_injected_config_is_the_cross_harness_authority(project: Path) -> None:
    path = autonomy.config_path(project)
    path.parent.mkdir(parents=True)
    path.write_text(
        """\
schema = "loop-os-config-v1"

[autonomy]
mode = "full_auto"
constitutional_jumps = "agent"
journal_recovery = "agent"
continue_until = "external_goal"
independent_review = true

[autonomy.grant]
approved_by = "operator"
statement = "delegate Loop OS autonomy"
granted_at = "2026-08-25T00:00:00Z"
""",
        encoding="utf-8",
    )

    grant = autonomy.load_grant(project, required_scope="continuous_goal")

    assert grant["source"] == "config"
    assert autonomy.status(project)["mode"] == "full_auto"


def test_config_precedes_enabled_legacy_grant(project: Path) -> None:
    _legacy_grant(project)
    autonomy.enable(project, "operator", "delegate Loop OS autonomy")
    autonomy.disable(project, "return to governed mode")

    with pytest.raises(autonomy.AutonomyError, match="disabled"):
        autonomy.load_grant(project)
    retired = json.loads(autonomy.legacy_grant_path(project).read_text(encoding="utf-8"))
    assert retired["enabled"] is False


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
