Stage 0 — 리포 준비 & 가드레일
- [x] feature 브랜치 생성
- [x] CQ 전용 디렉토리 추가
- [x] CLI `run-cq` 엔트리 추가
- [x] 기존 ELF 경로 회귀 테스트 보존 (백로그 `CQ-BG-001`, `tests/integration/test_cli_run_simulate.py`)

## Stage 1 — 최소 스펙 정의
- [x] `isa.yaml`: TE_GEMM, DMA_2D, FENCE_SPM
- [x] `cq.schema.json`: cmd_id, opcode, operands, deps, trace
- [x] 샘플 CQ.jsonl 파일 생성
- [x] Lint & Schema 검증 통과

## Stage 2 — CQ I/O + 실행 골격
- [x] `cq/io.py`: JSONL reader/writer
- [x] CLI `run-cq path/to/trace.jsonl`
- [x] trace_id 체계 (ir_id → isa_idx → cmd_id) (백로그 `CQ-BG-005`, `src/cq/trace.py`)

## Stage 3 — Dispatcher CQ Consumer
- [x] `src/cq/dispatcher.py` 구현 (스켈레톤, 상태 추적 포함)
- [x] CQ 엔트리 상태 전이 (queued→scheduled→done)
- [x] trace_id 로깅
- [x] 요약 통계 (num_cmds, avg_queue_wait)
- [x] 통합 테스트 `tests/integration/test_cq_dispatcher.py`로 기본 흐름 검증
- [x] `AdaptiveSimulator.run_cq_trace` 액션 로거 스텁
- [x] CQ DMA/GEMM 실행이 버스/NPU 클러스터 타이밍과 연동

## Stage 4 — 자원/타이밍/경합 모델
- [x] spm.py: bank/port 충돌 (백로그 `CQ-BG-003`, `src/cq/models/spm.py`)
- [x] bus.py: slice 단위 모델 (백로그 `CQ-BG-003`, `src/cq/models/bus.py`)
- [x] dma.py: row-based 지연 (백로그 `CQ-BG-003`, `src/cq/models/dma.py`)
- [x] te.py: GEMM 지연 근사 (백로그 `CQ-BG-003`, `src/cq/models/te.py`)
- [x] Deadlock 감지 로직 (백로그 `CQ-BG-003`, `src/cq/dispatcher.py`)
- [x] CQ vs ELF 비교 스텁 (`src/simulator/cq_runner.py`) 마련
- [x] CQ 텐서 초기화/실데이터 주입 (`AdaptiveSimulator.load_cq_tensors`)
- [x] 디스패처 자원 스케줄링 통합 (백로그 `CQ-BG-003`, `src/cq/dispatcher.py`, `src/simulator/main.py`)

## Stage 5 — Spec-Codegen v1
- [x] `isa.yaml` → dataclass 자동 생성 (백로그 `CQ-BG-002`, `src/scripts/generate_cq_models.py`, `src/cq/generated/isa_operands.py`)
- [x] `cq.schema.json` → Pydantic 모델 생성 (백로그 `CQ-BG-002`, `src/cq/generated/command_model.py`)

## Stage 6 — IR→ISA & ISA→CQ 변환
- [x] `rules/*.yaml`: Conv/Copy 룰 정의 (백로그 `CQ-BG-005`, `src/cq/rules/*.yaml`)
- [x] mapper.py: 룰 엔진 구현 (백로그 `CQ-BG-005`, `src/cq/mapper.py`)
- [x] cq/generator.py: ISA → CQ 변환 (백로그 `CQ-BG-005`, `src/cq/generator.py`)

## Stage 7 — Accuracy Guard & Golden Test
- [x] 골든 워크로드 5종 준비 (백로그 `CQ-BG-006`) — manifest/traces/configs/summaries 초안 확보 (`workloads/golden/*`)
- [x] golden diff CI 통합 (백로그 `CQ-BG-006`) — GitHub Actions 워크플로(`.github/workflows/cq-accuracy.yml`)에서 `scripts.check_cq_accuracy` 실행 및 JSON 리포트 업로드
- [x] 허용 편차 정책 설정 (백로그 `CQ-BG-006`) — Guard 활성화 및 ±5% 임계값 적용 (`workloads/golden/configs/*.json`)

## Stage 8 — 모델 정밀도/정책 확장
- [x] 스케줄 정책 (RR, EDF) (백로그 `CQ-BG-007`) — RR/EDF 정책 선택기를 `src/cq/scheduler.py`, `src/cq/dispatcher.py`에 도입하고 구성 값(`simulator.config.cq.dispatcher.policy`)과 CLI 플래그(`--cq-policy`, `--cq-lane-limit`, `--simulate`)로 전환 가능하도록 노출, 단위/통합 테스트(`tests/unit/test_cq_scheduler_policy.py`, `tests/unit/test_cli_cq_overrides.py`, `tests/integration/test_cli_run_cq.py`)로 검증 완료.
- [x] 멀티-TE, 멀티-DMA lane (백로그 `CQ-BG-007`) — 레인 용량 제한(`lane_limits`) 및 `dispatch.lane_usage` 통계를 실행 요약/골든 리포트에 반영(`scripts.check_cq_accuracy`, `workloads/golden/summaries/*.json`)하여 CQ 병렬 스케줄링 회귀를 Accuracy Guard로 모니터링 가능.

## Stage 9 — 문서화/시각화
- [x] ISA/CQ Reference 자동 생성 (백로그 `CQ-BG-008`) — Stage 8 자산을 기반으로 ISA/CQ 명세를 자동 수집해 `docs/reference/isa_cq_reference.md` 작성 (`stage9_doc_plan.md`)
- [x] Gantt chart/Timeline CSV 산출 (백로그 `CQ-BG-008`) — CQ 실행 타임라인을 CSV/시각화로 제공하는 도구 및 노트북 준비 (`stage9_doc_plan.md`)
- [x] 튜토리얼 노트북 작성 (백로그 `CQ-BG-008`) — `run-cq --simulate`, Accuracy Guard, 레인 통계 해석을 통합한 워크플로 문서화 (`docs/tutorials/cq_pipeline.md`, `stage9_doc_plan.md`)

## Stage 10 — Conv→GEMM 확장
- [x] ISA 업데이트 및 코드젠 반영 (`specs/isa.yaml`, `src/cq/generated/*`, `docs/reference/isa_cq_reference.md`, `stage10_conv_plan.md`)
- [x] Conv IR→CQ 매핑 규칙 및 단위 테스트 (`src/cq/rules/conv.yaml`, `tests/unit/test_cq_mapper_conv.py`)
- [x] Conv CQ 샘플/골든 자산 + 시뮬레이터 통합 (`workloads/cq/sample_conv.*`, `workloads/golden/`, `tests/integration/test_cli_run_cq.py`, `docs/tutorials/cq_pipeline.md`)
