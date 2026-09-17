"""Exercise the existing artifact lane used by the frame-exploration skill.

These checks prove handoff/provenance and authority boundaries, not the quality
of LLM-generated mechanisms. Behavioral review of the skill is separate.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import aim
import journal
import note
from _canon import digest_bytes
from seal import seal_contract
from tests.conftest import write_contract

ROOT = Path(__file__).parents[1]


def _cli(script: str, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(ROOT / "os" / script), *args],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def _comparison() -> dict:
    return {
        "baseline": {"approach": "decrement", "bottleneck": "one unit per step"},
        "abstraction": {"goal": "reduce distance to zero", "constraint": "keep app.py"},
        "search": {"candidate_limit": 2, "passes_used": 1},
        "candidates": [
            {
                "id": "C1", "mechanism": "direct decrement",
                "structural_mapping": "one step reduces distance by one",
                "transfer_break": "the objective is not monotone",
                "falsifier": "a decrement increases the measured value",
                "minimal_experiment": "one instrumented decrement",
            },
            {
                "id": "C2", "mechanism": "remove the application",
                "transfer_break": "violates the app-intact guard",
            },
        ],
        "comparison": [
            {"candidate_id": "C1", "decision": "select", "reason": "valid intervention"},
            {"candidate_id": "C2", "decision": "reject", "reason": "goal weakening"},
        ],
        "selection": {"candidate_id": "C1", "reason": "preserves the original task"},
    }


def test_initial_comparison_seals_before_contract_and_stays_advisory(
    project: Path, objective: Path, agent: Path,
) -> None:
    record = _comparison()
    draft = project / "exploration.json"
    draft.write_text(json.dumps(record), encoding="utf-8")
    assert not (project / ".journal").exists()  # draft works before bootstrap
    _cli("journal.py", "bootstrap", "--project", str(project), "--project-id", "toy")
    sealed = _cli("note.py", "--project", str(project), "--kind", "idea", "--body", str(draft))
    verified = note.load_notes(project)
    assert verified[0]["note_id"] == sealed["note_id"]
    assert verified[0]["body"] == record

    contract = write_contract(project, objective, agent)
    contract.write_text(
        f"# exploration: {sealed['note_id']}; selected: C1\n" + contract.read_text(),
        encoding="utf-8",
    )
    seal_contract(project)
    issued = aim.issue(project)
    spec = yaml.safe_load((project / issued["spec_path"]).read_text())
    assert spec["stages"][0]["prompt"] == "Lower the number in value.txt by exactly 1."
    assert "remove the application" not in json.dumps(spec)
    assert journal.replay(project).drawn_by_generation == {1: 3}
    assert [e["kind"] for e in journal.load_events(project)][:3] == [
        "bootstrap.v1", "note_sealed.v1", "contract_registered.v1",
    ]


def test_successor_dossier_carries_all_alternatives_and_direct_priors(
    registered_project: Path, tmp_path: Path,
) -> None:
    project = registered_project
    source = b"Synthetic source: removing app.py violates the task."
    prior = note.record(project, "external_evidence", {
        "summary": source.decode(), "source_locator": "fixture://task-constraints",
        "snapshot_digest": digest_bytes(source), "claims": ["app.py must remain"],
        "limitations": "synthetic plumbing evidence, not a scientific source",
    }, [])
    exploration = _comparison()
    idea = note.record(project, "idea", exploration, [])
    rival_body = {
        "commitment_rejected": "all steps must reduce by exactly one",
        "proposed_frame": "bounded larger decrements",
        "mechanism": "test whether larger steps keep monotonic progress",
        "falsifier": "larger decrements violate a guard or lose progress",
        "exploration": exploration,
    }
    # A comparison note does not implicitly forward its source to the dossier.
    with pytest.raises(note.NoteError, match="prior binding"):
        note.record(project, "rival_draft", rival_body, [idea["note_id"]])
    before = journal.replay(project)
    draft = tmp_path / "rival.json"
    draft.write_text(json.dumps(rival_body), encoding="utf-8")
    sealed = _cli("note.py", "--project", str(project), "--kind", "rival_draft",
                  "--body", str(draft), "--refs", prior["note_id"], idea["note_id"])
    packet = _cli("steer.py", "dossier", "--project", str(project), "--rival", sealed["note_id"])
    assert packet["rival_draft"]["body"]["exploration"] == exploration
    assert packet["external_priors"][0]["note_id"] == prior["note_id"]
    assert packet["external_priors"][0]["body"]["snapshot_digest"] == digest_bytes(source)
    after = journal.replay(project)
    assert after.generation == before.generation
    assert after.drawn_by_generation == before.drawn_by_generation
    assert after.adoptions == before.adoptions
    assert packet["current_frame"]["class"] == "toy_descent"
