---
name: loop-os
description: Loop OS의 outer loop 프로그램. agent(Claude Code/Codex)가 계기(instruments)를 실행하고 판단 파일을 저작하여 kernel loop을 조준한다. 프로젝트에 .journal/과 contract.toml이 있거나 만들려 할 때 사용.
---

# Loop OS — outer loop 프로그램

너(agent)는 outer loop의 런타임이다. 결정론 계기를 실행하고, 판단을 **파일로만**
저작한다. 계기가 거부하면 그 거부 사유가 곧 다음 할 일이다 — 우회하지 말 것.

계기는 Loop OS repo 루트(`~/loop-os`)에서 경로로 실행한다: `uv run python os/<계기>.py`.
`os/`는 python 패키지가 아니다 — 항상 스크립트 경로로 실행한다.

## 절대 규칙

1. `.journal/events.jsonl`을 직접 쓰지 않는다. 계기만 append한다. (수정하면 hash
   chain과 anchor가 증거를 남긴다.)
2. `spec.yaml`을 손으로 쓰지 않는다. `os/aim.py`만 spec을 방출한다.
3. kernel 엔진(`kernel/loop.py`)을 수정하지 않는다. upstream은 `infocz/gos`,
   갱신 절차는 `kernel/README.md`.
4. 판단(진단·노트·리뷰·계약 초안)은 파일로 저작하고 seal 계기로 봉인한다. 봉인되지
   않은 판단은 존재하지 않는 것과 같다.
5. 예산은 발행 시 인출되고 환불되지 않는다. `R5_BUDGET` 거부는 우회 대상이 아니라
   generation의 정직한 종착 상태다 — successor generation(jump)만이 예산을 다시 연다.
6. seal 사이클을 마칠 때마다 `os/journal.py anchor`를 실행하고 `.journal-anchor.json`을
   커밋한다 — head가 git 역사에 앵커되어야 chain의 tail-edit 사각이 닫힌다.

## 사이클

프로젝트 루트를 `$P`라 하자.

```
0. (최초 1회) uv run python os/journal.py bootstrap --project $P --project-id ID [--lineage name=digest ...]
   계약 저작 → uv run python os/seal.py contract --project $P --contract $P/<계약경로>
1. uv run python os/journal.py verify --project $P    # chain + anchor 검증. 깨졌으면 즉시 사용자에게 보고
2. uv run python os/journal.py status --project $P    # next_required가 다음 행동을 지시한다
3. uv run python os/aim.py --project $P --contract <계약>   # spec 방출. 거부 코드별 대응은 아래 표
4. spec을 git commit                                  # kernel은 untracked in-worktree spec을 거부
5. uv run python kernel/loop.py --repo $P run <spec_path>
6. uv run python os/seal.py run --project $P --summary <spec옆 summary.json> \
     --ledger $P/.git/experiment-loop/<loop_id>/ledger.jsonl [--trials <trials.jsonl>]
7. 진단 파일 저작 (아래 형식) → uv run python os/seal.py diagnosis --project $P --file <진단.json>
8. 관찰이 있으면 note 저작 → uv run python os/note.py --project $P --kind <kind> --body <파일> [--refs ...]
9. uv run python os/steer.py frame-health --project $P   # interpretation_requests 3개에 답한다:
   yes로 판단한 항목은 지시된 note kind로 기록한다 (stagnation→anomaly,
   assumption_misfit→assumption_conflict, frame_misfit→rival_draft)
10. uv run python os/memory.py extract --project $P      # 진단을 claim으로 증류
11. uv run python os/journal.py anchor --project $P → .journal-anchor.json 커밋
12. 2로 돌아간다
```

세션이 죽어도 상태는 파일이 전부다: 새 세션은 1→2만 실행하면 정확히 이어받는다.

## aim 거부 코드별 대응

| 코드 | 뜻 | 행동 |
| --- | --- | --- |
| R1_JOURNAL | journal 없음/체인 파손 | bootstrap 하거나, 파손이면 사용자에게 보고 (증거 사고) |
| R2_CONTRACT | 계약 미등록/드리프트 | `os/seal.py contract`로 등록, 드리프트면 원문 복원 또는 재등록 |
| R3_PENDING_RUN | 미봉인 run 존재 | run을 실행·봉인하거나, 실행 불능이면 `os/seal.py abandon` (예산은 소각) |
| R4_PENDING_DIAGNOSIS | 진단 미봉인 | 진단 저작 → 봉인 |
| R5_BUDGET | generation 예산 소진 | 우회 금지. residual → jump 경로 검토 |

## 진단 파일 형식

run의 증거(summary, ledger, agent 로그)를 읽고 저작한다. 모든 필드 필수, `REPLACE_ME` 금지.

```json
{
  "verdict": "SUPPORTED | REJECTED | INCONCLUSIVE",
  "what_moved": "objective가 얼마에서 얼마로, 몇 iterations, 분모",
  "mechanism_interpretation": "왜 움직였는가/안 움직였는가 — 계약의 mechanism 대비",
  "counterfactual": "변경이 없었으면 무엇이 관측됐을 것인가와 그 근거",
  "next_question": "이 결과가 여는 다음 질문"
}
```

`VALIDATED`라는 단어는 이 시스템의 어휘가 아니다. 진짜 판정(forward window 등)은
OS 밖에서 1회 일어나며, 여기의 verdict는 run 단위 가설 판정일 뿐이다.

## note kinds

| kind | 요건 |
| --- | --- |
| observation / anomaly / assumption_conflict | signal-bearing — `--refs`에 증거(이벤트 id/digest) 필수 |
| idea | 자유 |
| external_evidence | summary/source_locator/snapshot_digest/claims/limitations 전부. OS는 fetch하지 않는다 — 검색은 네가 밖에서 하고 digest만 들어온다 |
| rival_draft | commitment_rejected/proposed_frame/mechanism/falsifier. external_evidence가 하나라도 있으면 prior binding — refs에 external_evidence id 인용 필수 |

## jump (frame 전환)

class가 닫히거나(REJECTED 3회) 예산이 종착이면:

```
1. uv run python os/steer.py residual --project $P     # 닫힌 class의 기각 mechanism 목록 + 과제
2. rival_draft note 저작 (prior binding 준수)
3. uv run python os/steer.py dossier --project $P --rival <note_id> → 파일로 저장
4. successor contract 저작 (generation = 현재 + 1)
5. 독립 리뷰: 별도 세션/모델 라우트에서 저작한 review.json
   {"reviewer": ..., "independent": true, "verdict": "PASS", "notes": ...}
6. 사람 승인: approval.json {"approved_by": ..., "statement": ...} — 사람이 쓴다.
   네가 대필하지 않는다.
7. uv run python os/jump.py adopt --project $P --dossier D --successor S --review R --approval A
8. os/seal.py contract로 successor 등록 → os/aim.py (새 generation 예산)
```

7의 채택 이벤트 없이는 8이 거부된다 (generation bump 게이트). 파일이 없으면 이벤트를
만들 수 없다 — 그것이 유일한 집행이다.

**revoke**: successor가 예산을 인출하기 전(첫 spec_issued 전)까지는 채택을 되돌릴 수 있다:
`uv run python os/jump.py revoke --project $P --adoption <adoption event id> --reason "..."`.
revoke는 그 채택을 인용한 등록까지 replay에서 무효화하고 frame을 직전 등록으로 되돌린다.
예산이 이미 인출됐으면 revoke는 거부된다 — 그때는 새 jump만이 정직한 경로다.

## 경계

배포·릴리스·자본 배분·라이브 트레이딩은 이 시스템의 어휘에 없다. 그런 요청은
journal에 기록될 수 없으며, OS 밖의 사람 결정이다.
