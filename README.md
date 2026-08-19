# Loop OS

loop 프레임워크를 kernel로 하는 3층 연구 시스템. 설계는 [docs/design.md](docs/design.md)가 정본이다.
(구 Research OS의 전면 재작성 후신 — 구 저장소는 폐기되었고, 그 EventLog head digest는
첫 application(alpha-factory)의 journal bootstrap lineage에 봉인되어 있다.)

```
Application  프로젝트 repo: contract.toml · evaluator · .journal/
OS           계기(instruments): journal · aim · seal · steer · note · memory · jump
Kernel       kernel/loop.py: bounded·reversible·budgeted hill-climb (gos에서 vendored)
```

> Kernel은 오르기만 하고, OS는 어디를 오를지만 정하고, journal은 얼마나 올랐다고
> 주장할 수 있는지만 정한다. LLM은 방향 제안과 해석을 파일로만 내고, 그 파일이
> 없으면 시스템은 구조적으로 멈춘다.

## 인터페이스

CLI 제품은 없다. outer loop의 런타임은 agent 하네스(Claude Code / Codex)이며,
agent는 [SKILL.md](SKILL.md)의 지시에 따라 계기를 실행하고 판단 파일을 저작한다.
`os/`는 python 패키지가 아니라 스크립트 디렉토리다 — 항상 이 repo 루트에서 경로로
실행한다 (`__init__.py`가 없으므로 stdlib `os` 모듈과 충돌하지 않는다).

```bash
uv run python os/journal.py bootstrap --project DIR --project-id ID
uv run python os/seal.py    contract  --project DIR
uv run python os/aim.py               --project DIR
uv run python kernel/loop.py --repo DIR run SPEC
uv run python os/seal.py    run       --project DIR --summary S --ledger L [--trials T]
uv run python os/seal.py    diagnosis --project DIR --file D.json
uv run python os/journal.py anchor    --project DIR   # head를 tracked 파일로 — 커밋
uv run python os/journal.py status    --project DIR
uv run python os/jump.py    adopt     --project DIR --dossier D --successor S --review R --approval A
uv run python os/jump.py    revoke    --project DIR --adoption EVENT_ID --reason TEXT
```

## 규칙 요약

- journal은 계기만 append한다. agent가 봉인된 역사를 수정하면 hash chain이 증거를 남긴다.
- chain의 유일한 사각(마지막 줄 편집)은 **anchor**가 닫는다: head digest를 tracked
  파일(`.journal-anchor.json`)로 내려 git 역사에 앵커한다. seal 사이클마다 anchor 후 커밋.
- 판단은 상태 전이가 아니라 파일이다. 순서는 데이터 의존(digest 인용)으로만 강제된다.
- 예산은 발행 시점에 인출되고 환불되지 않는다 (reserved-not-measured).
- 채택(adoption)은 successor가 예산을 인출하기 전까지만 **revoke** 가능하다. revoke는
  그 채택을 인용한 등록까지 replay에서 무효화한다.
- kernel 엔진은 여기서 수정하지 않는다 — upstream은 `infocz/gos`, `kernel/VENDOR.json` 참조.

## 테스트

```bash
uv run pytest -q            # OS 계기 스위트
uv run pytest kernel/tests/ -q   # kernel 계약 스위트 (vendored)
```
