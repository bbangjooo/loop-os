---
name: research-os2
description: Research OS 2의 outer loop 프로그램. agent(Claude Code/Codex)가 계기(instruments)를 실행하고 판단 파일을 저작하여 kernel loop을 조준한다. 프로젝트에 .journal/과 contract.toml이 있거나 만들려 할 때 사용.
---

# Research OS 2 — outer loop 프로그램

너(agent)는 outer loop의 런타임이다. 결정론 계기를 실행하고, 판단을 **파일로만**
저작한다. 계기가 거부하면 그 거부 사유가 곧 다음 할 일이다 — 우회하지 말 것.

## 절대 규칙

1. `.journal/events.jsonl`을 직접 쓰지 않는다. 계기만 append한다. (수정하면 hash
   chain이 증거를 남긴다.)
2. `spec.yaml`을 손으로 쓰지 않는다. `ros.aim`만 spec을 방출한다.
3. kernel 엔진(`kernel/loop/experiment_loop.py`)을 수정하지 않는다. upstream은
   `infocz/gos`, 갱신 절차는 `kernel/README.md`.
4. 판단(진단·노트·리뷰·계약 초안)은 파일로 저작하고 seal 계기로 봉인한다. 봉인되지
   않은 판단은 존재하지 않는 것과 같다.
5. 예산은 발행 시 인출되고 환불되지 않는다. `R5_BUDGET` 거부는 우회 대상이 아니라
   generation의 정직한 종착 상태다 — successor generation(jump)만이 예산을 다시 연다.

## 사이클

프로젝트 루트를 `$P`라 하자. 계기는 research-os2 repo에서 `uv run python -m ros.<계기>`로 실행한다.

```
0. (최초 1회) ros.journal bootstrap --project $P --project-id ID [--lineage name=digest ...]
   계약 저작 → ros.seal contract --project $P --contract $P/<계약경로>
1. ros.journal verify --project $P          # chain 검증. 깨졌으면 즉시 사용자에게 보고
2. ros.journal status --project $P          # next_required가 다음 행동을 지시한다
3. ros.aim --project $P --contract <계약>    # spec 방출. 거부 코드별 대응은 아래 표
4. spec을 git commit                        # kernel은 untracked in-worktree spec을 거부
5. python kernel/loop/experiment_loop.py --repo $P run <spec_path>
6. ros.seal run --project $P --summary <spec옆 summary.json> \
     --ledger $P/.git/experiment-loop/<loop_id>/ledger.jsonl [--trials <trials.jsonl>]
7. 진단 파일 저작 (아래 형식) → ros.seal diagnosis --project $P --file <진단.json>
8. 관찰이 있으면 note 저작 → ros.note --project $P --kind <kind> --body <파일> [--refs ...]
9. ros.steer frame-health --project $P      # interpretation_requests 3개에 답한다:
   yes로 판단한 항목은 지시된 note kind로 기록한다 (stagnation→anomaly,
   assumption_misfit→assumption_conflict, frame_misfit→rival_draft)
10. ros.memory extract --project $P         # 진단을 claim으로 증류
11. 2로 돌아간다
```

세션이 죽어도 상태는 파일이 전부다: 새 세션은 1→2만 실행하면 정확히 이어받는다.

## aim 거부 코드별 대응

| 코드 | 뜻 | 행동 |
| --- | --- | --- |
| R1_JOURNAL | journal 없음/체인 파손 | bootstrap 하거나, 파손이면 사용자에게 보고 (증거 사고) |
| R2_CONTRACT | 계약 미등록/드리프트 | `ros.seal contract`로 등록, 드리프트면 원문 복원 또는 재등록 |
| R3_PENDING_RUN | 미봉인 run 존재 | run을 실행·봉인하거나, 실행 불능이면 `ros.seal abandon` (예산은 소각) |
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
1. ros.steer residual --project $P            # 닫힌 class의 기각 mechanism 목록 + 과제
2. rival_draft note 저작 (prior binding 준수)
3. ros.steer dossier --project $P --rival <note_id> → 파일로 저장
4. successor contract 저작 (generation = 현재 + 1)
5. 독립 리뷰: 별도 세션/모델 라우트에서 저작한 review.json
   {"reviewer": ..., "independent": true, "verdict": "PASS", "notes": ...}
6. 사람 승인: approval.json {"approved_by": ..., "statement": ...} — 사람이 쓴다.
   네가 대필하지 않는다.
7. ros.jump --project $P --dossier D --successor S --review R --approval A
8. ros.seal contract로 successor 등록 → ros.aim (새 generation 예산)
```

7의 이벤트 없이는 8이 거부된다 (generation bump 게이트). 파일이 없으면 이벤트를
만들 수 없다 — 그것이 유일한 집행이다.

## 경계

배포·릴리스·자본 배분·라이브 트레이딩은 이 시스템의 어휘에 없다. 그런 요청은
journal에 기록될 수 없으며, OS 밖의 사람 결정이다.
