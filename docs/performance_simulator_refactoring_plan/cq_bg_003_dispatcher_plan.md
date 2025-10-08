# CQ-BG-003 · CQ 디스패처 자원 스케줄링 통합 메모

## 1. 목표 및 범위
- CQ 디스패처가 단순 FIFO 처리에서 벗어나 자원 모델(SPM, Bus, DMA, TE)과 실시간으로 상호작용하도록 확장한다.
- 기존 `AdaptiveSimulator.run_cq_trace` 내 임시 액션 실행 로직을 디스패처와 명확히 분리하고, 이벤트 스케줄링을 일관되게 관리한다.
- Stage 4 체크리스트의 미완료 항목(디스패처 자원 스케줄링 통합)을 해소할 수 있을 만큼 구조를 구체화한다.

## 2. 현재 구조 정리
- `src/cq/dispatcher.py`: dependency 검증 및 상태 추적만 수행하는 스텁 구현, TODO에 자원 연동 계획이 남아 있음.
- `src/simulator/main.py`: CQ 액션을 직접 실행하며 DMA/TE 모델과 상호작용한다. 디스패처를 우회하여 실제 자원 사용 처리.
- `src/cq/models/*`: bus/dma/spm/te 모델이 개별 메서드로 동작하며 현재는 시뮬레이터가 직접 호출.

## 3. 변경 제안
### 3.1 설계 방향
1. **액션 빌더 분리**: `build_execution_plan` 결과를 디스패처가 소비 가능한 작업 큐로 변환.
2. **자원 인터페이스 정의**: 디스패처 ↔ 시뮬레이터 사이에 최소한의 프로토콜(예: `schedule_dma`, `schedule_gemm`)을 규정.
3. **이벤트 루프 공유**: 디스패처가 이벤트 타임라인을 제어할 수 있도록 시뮬레이터의 시간 동기화 API를 노출.

### 3.2 단계별 작업
- **T1**: 디스패처 스케줄링 설계 확정 및 이벤트 흐름 정의
  - 인터페이스 초안 (`src/cq/dispatcher.py` 내 Proto 클래스 또는 TypedDict) 작성
  - 상태 머신 다이어그램을 작성하고 Stage checklist에 첨부
- **T2**: 리소스 모델과 디스패처 통신 계층 구현
  - `AdaptiveSimulator`에서 자원 모델 접근자를 제공하는 어댑터 작성
  - 디스패처가 DMA/GEMM 요청을 처리할 때 해당 어댑터 메서드를 호출하도록 수정
- **T3**: 통합 테스트 확장
  - 기존 `test_cq_dispatcher.py`에 경합/지연 시나리오 추가
  - `tests/integration/test_cli_run_cq.py`에 큐 대기시간 단언을 보강

## 4. 리스크 & 대응
- **시간 동기화 복잡도**: 이벤트 스케줄러와 디스패처 간 충돌 → 최소한의 단계로 incremental integration (시뮬레이터 wrapper 제공)
- **회귀 위험**: 기존 CQ 경로 및 ELF 경로 영향 → golden workload 준비 전 interim regression fixture 추가 필요

## 5. 산출물 체크리스트
- [x] 디스패처 ↔ 시뮬레이터 인터페이스 문서화 (`docs/performance_simulator_refactoring_plan/cq_bg_003_dispatcher_plan.md` 보완)
- [x] `src/cq/dispatcher.py`에 새로운 상태 전이/자원 요청 로직 반영
- [x] 통합 테스트 및 신규 시나리오 업데이트 완료 (`ia_risc_v_npu/tests/integration/test_cq_dispatcher.py`)
- [x] CLI 및 CQ 비교 경로 검증 (`pytest ia_risc_v_npu/tests/integration/test_cli_run_cq.py`, `pytest ia_risc_v_npu/tests/unit/test_cq_runner.py`)

## 6. 후속 작업 제안
- [x] 경합/지연 시나리오를 다루는 CQ 통합 테스트 추가 (`test_cq_dma_contention_roundtrip`, 동일 DMA 왕복 검증)
- [ ] CLI 및 `compare_cq_vs_elf` 문서에 dispatcher 기반 실행 플로우 요약 추가 (`workloads/cq/README.md`, `docs/tutorials/cq_pipeline.md`)
