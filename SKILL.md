---
name: loop-os
description: Loop OS의 outer loop 프로그램. agent(Claude Code/Codex)가 계기(instruments)를 실행하고 판단 파일을 저작하여 kernel loop을 조준한다. 프로젝트에 .journal/과 contract.toml이 있거나 만들려 할 때 사용.
---

# Loop OS — outer loop 프로그램

너(agent)는 outer loop의 런타임이다. 결정론 계기를 실행하고, 판단을 **파일로만**
저작한다. 계기가 거부하면 그 거부 사유가 곧 다음 할 일이다 — 우회하지 말 것.

계기는 Loop OS repo 루트(`~/loop-os`)에서 경로로 실행한다: `uv run python os/<계기>.py`.
`os/`는 python 패키지가 아니다 — 항상 스크립트 경로로 실행한다.

## Program first

Loop OS 대상 프로젝트는 첫 contract 전에 루트에 `program.md`를 가져야 한다.
`program.md`는 GJC deep-interview에서 forked/adapted된 standalone program interview가
작성하는 장기 연구 계획이다. GJC가 설치되어 있지 않아도 `/loop-os:program`으로
작성할 수 있다.

```
/loop-os:program → program.md → /loop-os:bootstrap → contract.toml → cycle
```

Program은 목표·연구 질문·허용 조작·성공 증거·falsifier·제약·비목표·사람에게
돌려줄 경계를 담는다. 실행 상태를 담지 않으며, contract가 현재 generation의
실행 frame을 소유한다. Program을 만들거나 정제하는 interview는 product code,
contract, journal, kernel을 수정하지 않는다.

새 계약은 `[program]`에 프로젝트 내부 경로 `path`와 원문의 SHA-256 `digest`를
명시한다. `seal contract`와 `aim`은 실제 파일을 확인하고, `aim`은 모든 stage에
프로그램 해시 guard를 넣는다. 등록 이후 프로그램을 바꾸어도 예산을 다시 받거나
성공 기준을 조용히 바꿀 수 없다. 기존 계약에 이 항목이 없으면 그대로 동작하며,
이미 발행된 run을 먼저 마친 뒤 검토된 후속 계약에서 연결한다.

프로그램에 기존 후보·잔여 신호·필수 후속 작업이 있으면 새로운 주제보다 먼저
그 처리 상태를 확인한다. 완료·기각·보류의 근거를 남기고, 해결되지 않은 항목을
진행 보고에서 없애지 않는다. 사용자 요구와 agent가 도입한 작업 가정을 구분한다.
자료 수집·도구 제작·검사 통과는 준비일 수 있으며 그 자체가 최종 성과는 아니다.

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
7. objective가 로컬에서 재계산 가능한 프로젝트라면, 계약 프롬프트에 **평가 계기 규칙**을
   반드시 넣는다: "모든 평가는 objective 명령을 통해서만; 오프라인 재계산·열거 금지;
   그럼에도 계기 밖에서 평가했다면 SUMMARY 줄에 `offline_evals=N`으로 선언". 선언이
   발견되면 `os/seal.py run --declared-evals N`으로 봉인한다 — 선언은 분모를 올릴 수만
   있다. (근거: bench 첫 LLM run에서 실증된 분모 우회, bench/README.md findings.)
8. 기본 모드는 사람 헌법 게이트와 journal 손상 중단을 유지한다. tracked
   `.loop-os/config.toml`의 `autonomy.mode = "full_auto"`인 프로젝트만 예외다.
   이 모드에서도 판단을 생략하지 않는다: constitutional jump는 구조화된 full_auto
   approval + 독립 리뷰, journal 손상은 구조화된 recovery decision + 원본 archive를
   남긴다. 자율성은 결정자를 바꿀 뿐 증거를 없애지 않는다.

## 사이클

프로젝트 루트를 `$P`라 하자.

```
0. (최초 1회) `/loop-os:program` → `$P/program.md` 작성
   `program.md`를 검토·commit한 뒤:
   uv run python os/journal.py bootstrap --project $P --project-id ID [--lineage name=digest ...]
   아래 Frame exploration → commands/contract.md의 계약·독립 리뷰·봉인 절차
0.5. uv run python os/autonomy.py status --project $P  # config-driven autonomy mode 확인
1. uv run python os/journal.py verify --project $P    # 기본: 깨지면 사용자 보고. full-auto: 아래 복구 절차
2. uv run python os/journal.py status --project $P    # next_required가 다음 행동을 지시한다
3. uv run python os/aim.py --project $P --contract <계약>   # spec 방출. 거부 코드별 대응은 아래 표
4. spec을 git commit                                  # kernel은 untracked in-worktree spec을 거부
5. uv run python kernel/loop.py --repo $P run <spec_path>
6. uv run python os/seal.py run --project $P --summary <spec옆 summary.json> \
     --ledger $P/.git/experiment-loop/<loop_id>/ledger.jsonl [--trials <trials.jsonl>]
7. 진단 파일 저작 (아래 형식) → uv run python os/seal.py diagnosis --project $P --file <진단.json>
8. 관찰이 있으면 note 저작 → uv run python os/note.py --project $P --kind <kind> --body <파일> [--refs ...]
9. uv run python os/steer.py frame-health --project $P   # frame 및 program 해석 요청에 답한다:
   각 if_judged_yes/no 조건에 따라 지시된 행동을 하고 note kind가 있으면 기록한다
   (stagnation→anomaly, assumption_misfit→assumption_conflict, frame_misfit→rival_draft)
10. uv run python os/memory.py extract --project $P      # 진단을 claim으로 증류
11. uv run python os/journal.py anchor --project $P → .journal-anchor.json 커밋
12. 2로 돌아간다
```

세션이 죽어도 상태는 파일이 전부다: 새 세션은 1→2만 실행하면 정확히 이어받는다.
수기 상태 문서가 오래되면 journal 기반 출력이 우선이다. `steer status`와
`frame-health`의 `program_progress`에서 최신 기준·변화·남은 작업·다음 행동을 읽는다.
기존 `next_required`는 절차상의 다음 단계이지 프로그램 성공 판정이 아니다.

## aim 거부 코드별 대응

| 코드 | 뜻 | 행동 |
| --- | --- | --- |
| R1_JOURNAL | journal 없음/체인 파손 | bootstrap. 파손이면 governed는 사용자 보고, full_auto는 복구 |
| R2_CONTRACT | 계약 미등록/드리프트 | `os/seal.py contract`로 등록, 드리프트면 원문 복원 또는 재등록 |
| R3_PENDING_RUN | 미봉인 run 존재 | run을 실행·봉인하거나, 실행 불능이면 `os/seal.py abandon` (예산은 소각) |
| R4_PENDING_DIAGNOSIS | 진단 미봉인 | 진단 저작 → 봉인 |
| R5_BUDGET | generation 예산 소진 | 우회 금지. residual → jump 경로 검토 |

## config-driven full-auto mode

full-auto는 별도 skill/command가 아니다. 기존 Loop OS 프로그램이 프로젝트의
`.loop-os/config.toml`을 읽어 실행 정책을 고른다. 정본 형식:

```toml
schema = "loop-os-config-v1"

[autonomy]
mode = "full_auto"
constitutional_jumps = "agent"
journal_recovery = "agent"
continue_until = "external_goal"
independent_review = true

[autonomy.grant]
approved_by = "<user>"
statement = "delegate constitutional jumps, journal recovery, and continuous goal execution to the agent"
granted_at = "<UTC timestamp>"
```

직접 config를 주입하거나 다음 계기로 동일한 canonical config를 만들 수 있다:

```
uv run python os/autonomy.py enable --project $P \
  --approved-by "user invoking loop-os full-auto" \
  --statement "delegate constitutional jumps, journal recovery, and continuous goal execution to the agent"
```

journal이 건강하면 즉시 `os/journal.py anchor --project $P`를 실행하고
`.loop-os/config.toml`과 `.journal-anchor.json`을 첫 aim 전에 commit한다. enable이
`PENDING_RECOVERY`를 반환하면 먼저 복구하고 같은 commit을 만든다. kernel은 깨끗한
tracked worktree를 요구한다.

그 뒤에는 한 cycle·한 generation이 끝났다는 이유로 멈추지 않는다. contract target과
guards 통과는 해당 generation의 candidate checkpoint일 뿐 외부 active goal 완료가
아니다. gate 수, `gates-failing=0`, metric deficit, trial 수, 예산 소진, generation
terminal을 active goal로 만들거나 그 완료 근거로 쓰지 않는다. 별도로 명시된 외부
goal의 결정론 완료 증거가 통과하고 이 project가 그 goal의 판정 owner일 때에만,
pending run/diagnosis 0, journal verify, 최종 anchor를 확인한 뒤 목표를 완료한다. 중앙
coordinator가 증거를 소유하면 lane은 coordinator나 사용자가 멈출 때까지 계속한다.
ordinary jump는 기존 auto 승인을 쓴다. constitutional jump는 사람을
기다리지 않고 독립 PASS 리뷰 뒤 다음 형식의 approval을 저작한다:

```json
{
  "mode": "full_auto",
  "decision": "헌법 변경이 최종 목표에 필요한 이유",
  "evidence": "dossier·실패·측정·리뷰 근거",
  "goal_continuity": "successor가 사용자의 최초 최종 결과를 계속 섬기는 이유",
  "risk_assessment": "성공 기준·예산·비교 가능성 위험",
  "rollback_plan": "첫 draw 전 revoke 또는 이후 corrective successor"
}
```

journal verify/anchor가 실패하면 원본을 직접 고치거나 삭제하지 않는다. 손상·anchor·git
역사·contract·ledger를 조사하고 아래 recovery decision을 파일로 저작한 뒤 계기를 쓴다:

```json
{
  "verdict": "RECOVER_AND_CONTINUE",
  "damage_assessment": "손상과 읽을 수 있는 범위",
  "evidence_considered": "조사한 증거",
  "continuation_rationale": "선택한 복구가 최선인 이유",
  "accepted_uncertainty": "복원하거나 독립 증명할 수 없는 것"
}
```

```
uv run python os/autonomy.py recover --project $P --decision <recovery.json> [--project-id ID]
```

계기는 원본 journal/anchor/config/decision을 `.journal/recovery/`에 보존하고, 읽을 수 있는
현재 event들을 canonical chain으로 재연결하고, `journal_recovered.v1`을 append한 뒤 새
anchor를 쓴다. 복구 후 `status.next_required`에서 즉시 재개한다. config rollback은
`os/autonomy.py disable --project $P --reason "..."`이다.

구형 `.loop-os-full-auto.json`은 한 migration window 동안만 fallback으로 읽는다.
`os/autonomy.py migrate --project $P`는 `.loop-os/config.toml`을 확장 생성하고 구형 파일은
삭제하지 않은 채 `enabled=false`로 retire한다. 신규 config가 있으면 항상 그것이 우선이다.

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

`[program]`에 연결된 spec의 진단에는 다음 블록도 필수다. `evidence_refs`는 이
진단의 run seal event id를 포함하는 기존 journal event id 목록이다. `criterion`은
프로그램의 실제 성공 증거 항목을 가리키고, `delta`는 그 항목이 얼마나 변했는지
또는 아직 변하지 않았는지를 쓴다. `remaining`은 빈 목록일 수 있지만 자동 완료를
뜻하지 않는다. 새 프로그램 연결 이전의 run·migrated run에는 소급 요구하지 않는다.

```json
{
  "program_progress": {
    "kind": "preparation",
    "criterion": "program.md / Success Evidence: 실제로 사용할 수 있는 결과",
    "delta": "입력 검사 도구는 완성했지만 사용할 수 있는 결과는 아직 0개",
    "evidence_refs": ["ev-실제-run-seal-id"],
    "remaining": ["기존 후보 재검증", "비교 기준선 확보"],
    "next_action": "완성한 검사 도구로 기존 후보의 재검증을 마친다"
  }
}
```

`kind`는 `outcome`(프로그램 결과), `learning`(가설 판단을 바꾸는 근거),
`preparation`(준비), `no_change`(변화 없음) 중 하나다. 이것은 저자의 판단이며,
OS는 형식과 증거 연결을 확인할 뿐 의미를 인증하지 않는다. 미보고는 변화 없음이
아니라 미확인이다. `SUPPORTED`나 `outcome` 선언 수로 최종 완료를 판정하지 않는다.
사용자 보고는 프로그램 성과와 준비·학습을 먼저 구분하고 frame 지표·예산을 덧붙인다.

`VALIDATED`라는 단어는 이 시스템의 어휘가 아니다. 진짜 판정(forward window 등)은
OS 밖에서 1회 일어나며, 여기의 verdict는 run 단위 가설 판정일 뿐이다.

## note kinds

| kind | 요건 |
| --- | --- |
| observation / anomaly / assumption_conflict | signal-bearing — `--refs`에 증거(이벤트 id/digest) 필수 |
| idea | 자유; 최초 frame의 후보 비교·선택 기록도 이 kind로 봉인 |
| external_evidence | summary/source_locator/snapshot_digest/claims/limitations 전부. OS는 fetch하지 않는다 — 검색은 네가 밖에서 하고 digest만 들어온다 |
| rival_draft | commitment_rejected/proposed_frame/mechanism/falsifier. external_evidence가 하나라도 있으면 prior binding — refs에 external_evidence id 인용 필수 |

## jump (frame 전환)

class가 닫히거나(REJECTED 3회) 예산이 종착이면 — 사람을 기다리지 말고 네가 스스로
이 절차를 실행한다 (`/loop-os:jump`가 한 번의 pass). ordinary jump는 트리거부터
승인까지 인간 개입 0이다. 기본 모드는 constitutional jump에서 사람을 부르지만,
full-auto config가 있으면 agent가 구조화된 승인을 저작한다:

```
1. uv run python os/steer.py residual --project $P     # 닫힌 class의 기각 mechanism 목록 + 과제
2. 아래 Frame exploration → 비교 기록 전체를 exploration 필드에 담은 rival_draft 봉인 (prior binding 준수)
3. uv run python os/steer.py dossier --project $P --rival <note_id> → 파일로 저장
4. successor contract 저작 (generation = 현재 + 1, [core]는 그대로 복사)
5. 독립 리뷰: 별도 컨텍스트의 blind subagent(가능하면 다른 모델 라우트)가 dossier와
   successor contract 두 파일만 보고 후보 비교·선택과 계약의 일치까지 검토한 review.json
   {"reviewer": ..., "independent": true, "verdict": "PASS", "notes": ...}
6. 승인 — 2단계:
   · ordinary jump: approval.json {"mode": "auto", "basis": "core-preserved"} —
     네가 써도 된다. os/jump.py가 파일과 journal에서 직접 재검증한다:
     [core] canonical 불변 · project.id/[revert] 유지 · budget 비인상 · stage
     objective 측정 필드(command/direction/margin/target/proxy_license) 집합
     동일 · 모든 successor stage가 현행 guard 전부를 각자 보유(decoy stage에
     몰아두기 불가) · top-level integrity가 현행 pin 전부(스테이지 pin 포함)를
     보유 · 현재 frame이 실제로 닫힘(class REJECTED 3회, 또는 예산 전량 인출 +
     모든 run 봉인/포기 + 진단 완료). 하나라도 어긋나면 auto는 거부된다.
   · constitutional jump (위 조건 밖 전부 — [core]·측정·guard 변경, 예산 인상,
     열린 frame에서의 jump): approval.json {"approved_by": ..., "statement": ...}
     — 기본 모드에서는 사람이 쓴다. full-auto mode에서는 위 `mode=full_auto` 형식을
     agent가 직접 쓰며 config digest와 approval digest가 adoption에 함께 봉인된다.
7. uv run python os/jump.py adopt --project $P --dossier D --successor S --review R --approval A
8. os/seal.py contract로 successor 등록 → os/aim.py (새 generation 예산)
```

`[core]`는 contract의 헌법이다 — goal 등 저자가 bootstrap에서 동결한 절. evaluator는
stages에 살지만 측정 필드는 헌법의 일부로 함께 동결된다 — 성공기준을 느슨하게
만드는 모든 경로(goal 문구, 측정 교체, guard 삭제)가 기본 모드에서는 사람 게이트를
지나고, full-auto에서는 명시 config + 독립 리뷰 + agent 판단 파일을 지난다. 등록된
contract에 [core]가 없으면 auto 단계 자체가 없다 — 모든 jump가 constitutional이다.
successor는 등록 contract와 **다른 경로**에 저작하라 — 등록된 텍스트가 제자리에
없으면 auto는 기준선을 세울 수 없어 거부된다. 채택 후 successor를 contract.toml로
복사해 등록하면 digest가 동일해 게이트를 그대로 통과한다.

7의 채택 이벤트 없이는 8이 거부된다 (generation bump 게이트). 파일이 없으면 이벤트를
만들 수 없다 — 그것이 유일한 집행이다.

**revoke**: successor가 예산을 인출하기 전(첫 spec_issued 전)까지는 채택을 되돌릴 수 있다:
`uv run python os/jump.py revoke --project $P --adoption <adoption event id> --reason "..."`.
revoke는 그 채택을 인용한 등록까지 replay에서 무효화하고 frame을 직전 등록으로 되돌린다.
예산이 이미 인출됐으면 revoke는 거부된다 — 그때는 새 jump만이 정직한 경로다.

## Frame exploration

최초 contract의 frame 선택 전, `residual → rival_draft` 사이, 또는 frame-health의
제안을 rival로 구체화할 때 [후보 탐색 절차](references/frame-exploration.md)를 읽고
실행한다. 일반 cycle의 매 iteration마다 반복하지 않는다. 기존 해법과 병목에서
출발해 추상화·근거리/원거리·구조적 유추·analogy-first·method-first·무작위 단서·
전제 뒤집기·실패 역산으로 후보를 만들고, 생성 뒤 별도로 비교·선택한다.

기록은 기존 `idea`/`rival_draft`를 사용한다. 선택된 후보뿐 아니라 대안·탈락 이유·
전이 실패 조건·최소 반증 실험을 독립 리뷰에 전달한다. 실제 평가는 기존 계약과
계기 예산을 따른다. 새로운 후보를 생각해냈다는 사실은 jump 승인이나 성능 증거가
아니다. 기록의 의미·탐색 다양성은 agent와 reviewer가 판단하며 계기는 인증하지 않는다.

## 경계

배포·릴리스·자본 배분·라이브 트레이딩은 이 시스템의 어휘에 없다. 그런 요청은
journal에 기록될 수 없으며, OS 밖의 사람 결정이다.
