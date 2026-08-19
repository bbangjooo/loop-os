from __future__ import annotations

import json
from pathlib import Path

import pytest

import journal
from _canon import canonical_json


def _boot(project: Path) -> None:
    journal.append_event(project, "bootstrap.v1", {"project_id": "toy", "lineage": []})


def test_bootstrap_and_verify_roundtrip(project: Path) -> None:
    _boot(project)
    events = journal.load_events(project)
    assert len(events) == 1
    assert events[0]["kind"] == "bootstrap.v1"
    assert events[0]["prev"] == journal.GENESIS


def test_bootstrap_is_not_repeatable(project: Path) -> None:
    _boot(project)
    with pytest.raises(journal.JournalError, match="already bootstrapped"):
        _boot(project)


def test_append_before_bootstrap_is_refused(project: Path) -> None:
    with pytest.raises(journal.JournalError, match="not bootstrapped"):
        journal.append_event(project, "note_sealed.v1", {})


def test_unknown_kind_is_refused(project: Path) -> None:
    _boot(project)
    with pytest.raises(journal.JournalError, match="unknown event kind"):
        journal.append_event(project, "made_up.v1", {})


def test_chain_links_every_line(project: Path) -> None:
    _boot(project)
    journal.append_event(project, "note_sealed.v1", {"n": 1})
    journal.append_event(project, "note_sealed.v1", {"n": 2})
    events = journal.load_events(project)
    assert len(events) == 3
    assert events[1]["prev"] != journal.GENESIS
    assert events[2]["prev"] != events[1]["prev"]


def test_editing_sealed_history_breaks_the_chain(project: Path) -> None:
    _boot(project)
    journal.append_event(project, "note_sealed.v1", {"n": 1})
    journal.append_event(project, "note_sealed.v1", {"n": 2})
    path = journal.journal_path(project)
    lines = path.read_text(encoding="utf-8").splitlines()
    middle = json.loads(lines[1])
    middle["body"]["n"] = 999
    lines[1] = canonical_json(middle)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(journal.JournalError, match="hash chain broken"):
        journal.load_events(project)


def test_tail_edit_is_the_documented_blind_spot(project: Path) -> None:
    """A canonical edit to the newest line, made before anything chains over
    it, is invisible to the chain itself — detection needs an external head
    anchor (a sealed head digest in a commit or a later citation). Kept as an
    explicit test so the limitation stays documented rather than assumed away."""
    _boot(project)
    journal.append_event(project, "note_sealed.v1", {"n": 1})
    path = journal.journal_path(project)
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace('"n":1', '"n":9'), encoding="utf-8")
    events = journal.load_events(project)
    assert events[-1]["body"]["n"] == 9


def test_non_canonical_line_is_refused(project: Path) -> None:
    _boot(project)
    path = journal.journal_path(project)
    event = json.loads(path.read_text(encoding="utf-8"))
    pretty = json.dumps(event, indent=2).replace("\n", " ")
    path.write_text(pretty + "\n", encoding="utf-8")
    with pytest.raises(journal.JournalError, match="canonical"):
        journal.load_events(project)


def test_truncated_tail_is_repaired_on_append(project: Path) -> None:
    _boot(project)
    journal.append_event(project, "note_sealed.v1", {"n": 1})
    path = journal.journal_path(project)
    with path.open("ab") as handle:
        handle.write(b'{"journal_schema":"ros2-journal-v1","half')
    journal.append_event(project, "note_sealed.v1", {"n": 2})
    events = journal.load_events(project)
    assert [e["body"].get("n") for e in events[1:]] == [1, 2]


def test_reduce_state_tracks_pending_obligations(project: Path) -> None:
    _boot(project)
    journal.append_event(
        project,
        "contract_registered.v1",
        {"contract_path": "contract.toml", "contract_digest": "d" * 64, "generation": 1, "class": "x"},
    )
    journal.append_event(
        project,
        "spec_issued.v1",
        {"loop_id": "x-g1-001", "spec_path": "s", "spec_digest": "a" * 64,
         "contract_digest": "d" * 64, "generation": 1, "class": "x",
         "proxy_licenses": ["clause"], "draw": 3},
    )
    state = journal.replay(project)
    assert list(state.pending_runs) == ["a" * 64]
    assert state.drawn_by_generation == {1: 3}

    run = journal.append_event(
        project, "run_sealed.v1", {"spec_digest": "a" * 64, "origin": "issued"}
    )
    state = journal.replay(project)
    assert not state.pending_runs
    assert list(state.pending_diagnoses) == [run["event_id"]]

    journal.append_event(
        project, "diagnosis_sealed.v1", {"run_seal_id": run["event_id"], "spec_digest": "a" * 64}
    )
    state = journal.replay(project)
    assert not state.pending_diagnoses


def test_anchor_catches_the_tail_edit(project: Path) -> None:
    """The blind spot documented above closes once the head is anchored: a
    canonical tail edit after anchoring makes the anchored head match no
    journal line, and verify fails closed."""
    _boot(project)
    journal.append_event(project, "note_sealed.v1", {"n": 1})
    journal.write_anchor(project)
    path = journal.journal_path(project)
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace('"n":1', '"n":9'), encoding="utf-8")
    with pytest.raises(journal.JournalError, match="anchor mismatch"):
        journal.check_anchor(project)


def test_anchor_tolerates_growth_after_anchoring(project: Path) -> None:
    _boot(project)
    journal.append_event(project, "note_sealed.v1", {"n": 1})
    journal.write_anchor(project)
    journal.append_event(project, "note_sealed.v1", {"n": 2})
    result = journal.check_anchor(project)
    assert result == {"anchored": True, "anchored_events": 2, "events_since_anchor": 1}


def test_anchor_refuses_a_broken_chain(project: Path) -> None:
    _boot(project)
    journal.append_event(project, "note_sealed.v1", {"n": 1})
    path = journal.journal_path(project)
    lines = path.read_text(encoding="utf-8").splitlines()
    middle = json.loads(lines[0])
    middle["body"]["project_id"] = "evil"
    lines[0] = canonical_json(middle)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(journal.JournalError):
        journal.write_anchor(project)  # never anchor what does not verify


def test_abandon_clears_pending_but_keeps_the_draw(project: Path) -> None:
    _boot(project)
    journal.append_event(
        project,
        "spec_issued.v1",
        {"loop_id": "x-g1-001", "spec_path": "s", "spec_digest": "a" * 64,
         "contract_digest": "d" * 64, "generation": 1, "class": "x",
         "proxy_licenses": ["clause"], "draw": 3},
    )
    journal.append_event(project, "run_abandoned.v1", {"spec_digest": "a" * 64, "reason": "crash"})
    state = journal.replay(project)
    assert not state.pending_runs
    assert state.drawn_by_generation == {1: 3}  # reserved, not refunded
