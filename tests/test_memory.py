from __future__ import annotations

import json
from pathlib import Path

import memory
from tests.test_steer import _cycle


def test_extract_is_idempotent(registered_project: Path, tmp_path: Path) -> None:
    _cycle(registered_project, tmp_path, 1, "REJECTED")
    first = memory.extract(registered_project)
    assert first == {"status": "CLAIMS_SEALED", "claims": 1, "event_id": first["event_id"]}
    again = memory.extract(registered_project)
    assert again["status"] == "NOTHING_TO_EXTRACT"


def test_claims_carry_provenance(registered_project: Path, tmp_path: Path) -> None:
    _cycle(registered_project, tmp_path, 1, "SUPPORTED")
    memory.extract(registered_project)
    claims = memory.load_claims(registered_project)
    assert len(claims) == 1
    claim = claims[0]
    assert claim["verdict"] == "SUPPORTED"
    assert claim["class"] == "toy_descent"
    assert claim["run_seal_id"].startswith("ev-")
    assert len(claim["diagnosis_digest"]) == 64


def test_retrieve_is_exact_class(registered_project: Path, tmp_path: Path) -> None:
    _cycle(registered_project, tmp_path, 1, "REJECTED")
    memory.extract(registered_project)
    assert memory.retrieve(registered_project, "toy_descent")["claims"]
    assert memory.retrieve(registered_project, "other_class")["claims"] == []


def test_tampered_claim_is_dropped(registered_project: Path, tmp_path: Path) -> None:
    _cycle(registered_project, tmp_path, 1, "REJECTED")
    memory.extract(registered_project)
    path = memory.claims_path(registered_project)
    path.write_text(path.read_text(encoding="utf-8").replace("REJECTED", "SUPPORTED"), encoding="utf-8")
    assert memory.load_claims(registered_project) == []


def test_incremental_extraction_across_cycles(registered_project: Path, tmp_path: Path) -> None:
    _cycle(registered_project, tmp_path, 1, "REJECTED")
    memory.extract(registered_project)
    _cycle(registered_project, tmp_path, 2, "INCONCLUSIVE")
    result = memory.extract(registered_project)
    assert result["claims"] == 1
    verdicts = sorted(c["verdict"] for c in memory.load_claims(registered_project))
    assert verdicts == ["INCONCLUSIVE", "REJECTED"]
