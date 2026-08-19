from __future__ import annotations

import json
from pathlib import Path

import pytest

from ros import journal, note


def test_note_requires_a_journal(project: Path) -> None:
    with pytest.raises(journal.JournalError):
        note.record(project, "idea", {"text": "x"}, [])


def test_signal_bearing_note_requires_evidence_refs(registered_project: Path) -> None:
    with pytest.raises(note.NoteError, match="signal-bearing"):
        note.record(registered_project, "anomaly", {"text": "odd"}, [])


def test_idea_needs_no_refs_and_is_sealed(registered_project: Path) -> None:
    result = note.record(registered_project, "idea", {"text": "try a shorter lookback"}, [])
    assert result["status"] == "NOTE_SEALED"
    notes = note.load_notes(registered_project)
    assert [n["kind"] for n in notes] == ["idea"]


def test_external_evidence_requires_all_fields(registered_project: Path) -> None:
    with pytest.raises(note.NoteError, match="snapshot_digest"):
        note.record(
            registered_project,
            "external_evidence",
            {"summary": "s", "source_locator": "url", "claims": ["c"], "limitations": "l"},
            [],
        )


def _evidence(project: Path) -> str:
    return note.record(
        project,
        "external_evidence",
        {
            "summary": "paper shows lead-lag decays after 2021",
            "source_locator": "doi:10.0/x",
            "snapshot_digest": "a" * 64,
            "claims": ["decay"],
            "limitations": "equities only",
        },
        [],
    )["note_id"]


def _rival_body() -> dict:
    return {
        "commitment_rejected": "responders catch up within L bars",
        "proposed_frame": "responders overshoot; fade the gap instead",
        "mechanism": "liquidity-driven overreaction",
        "falsifier": "gap continues in the catch-up direction after signal",
    }


def test_prior_binding_activates_with_first_external_evidence(registered_project: Path) -> None:
    # Before any external evidence: a rival draft needs no prior.
    free = note.record(registered_project, "rival_draft", _rival_body(), [])
    assert free["status"] == "NOTE_SEALED"
    evidence_id = _evidence(registered_project)
    with pytest.raises(note.NoteError, match="prior binding"):
        note.record(registered_project, "rival_draft", _rival_body(), [])
    bound = note.record(registered_project, "rival_draft", _rival_body(), [evidence_id])
    assert bound["status"] == "NOTE_SEALED"


def test_tampered_note_is_dropped_by_load(registered_project: Path) -> None:
    note.record(registered_project, "idea", {"text": "original"}, [])
    path = note.notes_path(registered_project)
    path.write_text(path.read_text(encoding="utf-8").replace("original", "tampered"), encoding="utf-8")
    assert note.load_notes(registered_project) == []


def test_note_content_never_enters_the_journal(registered_project: Path) -> None:
    note.record(registered_project, "idea", {"text": "secret-advisory-content"}, [])
    raw = journal.journal_path(registered_project).read_text(encoding="utf-8")
    assert "secret-advisory-content" not in raw  # only the digest is sealed
    assert "note_sealed.v1" in raw
