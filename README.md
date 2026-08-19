# Research OS 2

loop 프레임워크를 kernel로 하는 3층 연구 시스템. 설계는 [docs/design.md](docs/design.md)가 정본이다.

```
Application  프로젝트 repo: contract.toml · evaluator · .journal/
OS           계기(instruments): journal · aim · seal · steer · note · memory · jump
Kernel       loop: bounded·reversible·budgeted hill-climb (gos에서 vendored)
```

> Kernel은 오르기만 하고, OS는 어디를 오를지만 정하고, journal은 얼마나 올랐다고
> 주장할 수 있는지만 정한다. LLM은 방향 제안과 해석을 파일로만 내고, 그 파일이
> 없으면 시스템은 구조적으로 멈춘다.

## 인터페이스

CLI 제품은 없다. outer loop의 런타임은 agent 하네스(Claude Code / Codex)이며,
agent는 skill의 지시에 따라 계기를 실행하고 판단 파일을 저작한다.

```bash
python -m ros.journal bootstrap --project DIR --project-id ID
python -m ros.seal    contract  --project DIR
python -m ros.aim               --project DIR
python kernel/loop/experiment_loop.py --repo DIR run SPEC
python -m ros.seal    run       --project DIR --summary S --ledger L [--trials T]
python -m ros.seal    diagnosis --project DIR --file D.json
python -m ros.journal status    --project DIR
```

## 규칙 요약

- journal은 계기만 append한다. agent가 봉인된 역사를 수정하면 hash chain이 증거를 남긴다.
- 판단은 상태 전이가 아니라 파일이다. 순서는 데이터 의존(digest 인용)으로만 강제된다.
- 예산은 발행 시점에 인출되고 환불되지 않는다 (reserved-not-measured).
- kernel 엔진은 여기서 수정하지 않는다 — upstream은 `infocz/gos`, `kernel/VENDOR.json` 참조.

## 테스트

```bash
uv run pytest -q
```
