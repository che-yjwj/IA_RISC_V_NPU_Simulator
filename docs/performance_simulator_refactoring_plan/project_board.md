# CQ Refactor Project Board

이 보드는 PRD/TDD 문서(`docs/performance_simulator_refactoring_plan/prd_tdd_simulator.md`)에 정의된 백로그 항목을 실행 단계별로 정리한 간이 칸반입니다. 실제 이슈 트래커를 사용할 때는 동일한 ID(`CQ-BG-00X`)를 이슈 제목이나 라벨에 반영해 주십시오.

## Todo
- [ ] **CQ-BG-004** · Conv→GEMM 변환 및 ISA/워크로드 확장 (Conv opcode, CQ workload)
- [ ] **CQ-BG-008** · ISA/CQ 레퍼런스 자동 생성, Gantt/Timeline CSV, 튜토리얼 노트북

## In Progress

## Done
- [x] **CQ-BG-007** · 스케줄 정책(RR/EDF) 및 멀티 lane 모델링 — 디스패처 정책/레인 구성 옵션(`src/cq/scheduler.py`, `src/cq/dispatcher.py`, CLI `--cq-policy`/`--cq-lane-limit`/`--simulate`)을 도입하고 `run-cq --simulate` 실행 경로 및 Accuracy Guard 골든 리포트(`workloads/golden/summaries/*.json`)에 `dispatch.lane_usage` 통계를 반영하여 병렬 스케줄링 회귀를 자동 검사 가능하도록 완료 (`tests/unit/test_cq_scheduler_policy.py`, `tests/unit/test_cli_cq_overrides.py`, `tests/integration/test_cli_run_cq.py`, `scripts.check_cq_accuracy`).
- [x] **CQ-BG-001** · 기존 ELF 실행 경로 회귀 테스트 자동화 및 결과 보존 (`tests/integration/test_cli_run_simulate.py`)
- [x] **CQ-BG-003** · 자원/타이밍/경합 모델 1차 구현 및 디스패처 통합 완료 (`src/cq/models/*`, `src/simulator/main.py`, `src/cq/dispatcher.py`)
- [x] **CQ-BG-002** · ISA/CQ spec 기반 dataclass/codegen 파이프라인 도입 (`src/scripts/generate_cq_models.py`, `src/cq/generated/*`, `src/cq/schema.py`, `src/cq/adapter.py`)
- [x] **CQ-BG-005** · IR→ISA→CQ trace ID 체인 구현 (`src/cq/trace.py`, `src/cq/mapper.py`, `src/cq/generator.py`, trace index & 변환 테스트)
- [x] **CQ-BG-006** · Golden 워크로드 5종 및 Accuracy Guard diff 통합 완료 (±5% 편차 정책을 `ia_risc_v_npu/workloads/golden/configs/*.json`에 명시하고 `ia_risc_v_npu/workloads/golden/summaries/*.json`, `.github/workflows/cq-accuracy.yml`과 연동)

## 사용 방법 메모
- 각 항목의 체크박스를 갱신하면 문서 내에서도 진행 상황을 추적할 수 있습니다.
- Git 이슈 보드를 병행할 경우, 동일한 ID를 라벨 또는 제목으로 사용해 상호 참조를 유지하세요.
- 칸반 업데이트 후 `prd_tdd_simulator.md`와 `stage_plan_checklist.md`의 관련 체크 항목도 함께 조정하면 문서 간 일관성이 보장됩니다.
