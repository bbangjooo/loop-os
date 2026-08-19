# Kernel — loop

Loop OS 설계(`docs/design.md`)의 Layer 0. bounded·reversible·budgeted hill-climb
실행기이며, 이 저장소에서 어떤 코드도 이 파일을 수정하지 않는다.

## 단일 소스 규칙

- **Upstream은 `infocz/gos`의 `loop/`다.** 이 디렉토리는 그 vendored 사본이며, 출처
  commit과 digest는 `VENDOR.json`에 고정된다.
- 엔진(`loop.py`)과 `template.yaml`은 upstream과 **byte-identical**해야 한다. 수정이
  필요하면 upstream(gos)에 반영한 뒤 다시 vendoring한다.
- 유일한 로컬 패치는 테스트 파일의 SCRIPT 경로 1줄(평탄화된 레이아웃 반영)이며
  `VENDOR.json`의 `local_patch`에 기록된다.

## 구성

| 파일 | 역할 |
| --- | --- |
| `loop.py` | 엔진 전체 (stdlib + PyYAML, 단일 파일) |
| `template.yaml` | spec 스키마의 source of truth (주석 포함) |
| `tests/test_loop.py` | 계약 테스트 스위트 — 엔진과 함께만 이동한다 |
| `VENDOR.json` | upstream commit + 파일별 sha256 (+ 로컬 패치 기록) |

## 갱신 절차

1. upstream에서 세 파일을 복사하고 이 레이아웃으로 배치한다 (테스트의 SCRIPT 경로
   1줄 재패치).
2. 테스트를 실행한다: `uv run pytest kernel/tests/ -q`
3. `VENDOR.json`의 commit과 digest를 갱신한다.
