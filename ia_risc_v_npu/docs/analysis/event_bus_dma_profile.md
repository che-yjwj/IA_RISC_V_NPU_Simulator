# Event Scheduler & Bus Profiling Summary

## Profiling setup
- Script: `workloads/profiling/event_bus_profile.py` (outputs JSON report to `workloads/profiling/event_bus_profile.json`)
- Workloads: three CNN kernels generated via `workloads.cnn_workload.generate_cnn_workload`
- Simulator entry point: `src/simulator/main.py:158` (`AdaptiveSimulator.run_simulation`)
- Metrics tapped:
  - Event queue instrumentation through `ProfilingEventScheduler`
  - Bus metrics and request traces from `src/simulator/memory.py:223`

## Event scheduler observations
- 여전히 `execute_instruction_event` 단일 콜백을 사용하지만, 각 이벤트 처리 직후 `flush_deferred_dma`가 호출되면서 NPU DMA가 동일 시각에 중첩될 수 있는 여지를 확인 (`src/simulator/main.py:170`)
- CNN 워크로드 기준 이벤트 큐 깊이는 최대 2까지 상승했으며, DMA flush 이벤트가 버스 요청을 즉시 재생하면서 CPU 파이프라인과 동기화를 유지
- 지연 DMA가 많은 시점에서는 동일 타임스탬프에서 다수의 DMA 재생이 발생하지만 힙 정렬로 안정적으로 처리됨

## Bus usage observations (CPU 시나리오)
- CPU 마스터(`0`)만 버스를 사용했고, CNN 워크로드별로 전송 요청은 2/14/11회(총 128/896/704바이트)로 집계
- 평균 대기 사이클 `0`, 최대 큐 깊이 `1`이며 슬라이스 기반 전송 지연은 `Bus._calculate_transfer_cycles` (`src/simulator/memory.py:389`)와 일치
- 큐가 늘어나지 않아 페치가 완전히 직렬화된 현재 파이프라인에서는 배치 최적화 이점이 없음

## NPU DMA 프로파일링
- 동일 시나리오(`issue_at` 0/40/80)에서 입력 DMA가 각각 0/40/80 사이클에 승인되어 연산이 즉시 시작됨 → `task_2`의 연산 완료(257)와 출력 완료(274)가 `task_1`의 출력 완료(308)보다 앞서면서 실제 겹침이 발생
- 재생된 타임라인 예시: `task_0` 입력 0→17, 연산 17→137, 출력 274→291; `task_1` 입력 40→57, 연산 57→177, 출력 291→308; `task_2` 입력 80→97, 연산 137→257, 출력 257→274
- 버스 통계: `avg_queue_depth = 1.0`, `avg_wait_cycles = 0.0`, `completed_requests = 6`; DMA 요청이 스케줄러에서 사전 정렬되어 대기 없이 처리됨
- 작업 완료 시각이 순차적이지 않기 때문에(예: `task_2.done_at = 274` < `task_0.done_at = 291`), 시뮬레이터 리포트에서는 역전된 완료 순서를 허용하도록 분석 스크립트 업데이트 완료

## CPU+NPU 버스 경합 실험
- 동일 합성 시나리오에서 버스 평균 대기는 `1.8` 사이클, 최대 큐 깊이는 `2`로 측정되어 CPU 요청이 NPU DMA에 의해 지연되는 구간을 확인
- DMA 지연 재생 덕분에 입력 DMA가 예정 시각에 도착하면서 CPU 요청이 DMA 완료를 기다리는 시간이 짧아졌고, `total_wait_cycles`는 `18`로 기존 대비 감소
- 미세한 대기는 여전히 존재하므로, 경합 환경에서의 파라미터 튜닝(슬라이스 크기, 우선순위)을 통해 추가 개선 가능

## Virtual DMA 스케줄러 실험
- VirtualBus는 여전히 `bus.now`에 구애받지 않고 스케줄링되며, 이제 실제 클러스터가 동일한 순서를 재생하도록 `_flush_cluster` 헬퍼를 도입해 결과 비교가 간단해짐 (`workloads/profiling/event_bus_profile.py:278`)
- VirtualBus 타임라인과 실제 버스 재생 타임라인이 동일한 완료 시각을 보고하여, 새 DMA 큐 구현이 결정적 순서를 재현함을 확인
- 대기 시간은 두 경우 모두 `0`으로 수렴하지만, 실제 버스에서는 CPU 경합 유무에 따라 다시 증가할 수 있음 → 향후 분석 시 조건을 명시해야 함

## Event-Driven DMA 프로토타입 설계
- 목표: `ClusterTask` 제출 시 입력 DMA를 즉시 예약하고, compute 진행 중에도 출력을 큐잉/재생하여 실제 버스에 순차 재생하는 어댑터 구현
- 구성 요소:
  - `NPUCluster` 내부에 `pending_dma` 큐를 추가하고, 실제 버스 호출 대신 이벤트 객체(`DeferredDMA`)를 축적
  - 시뮬레이터 메인 루프에서 주기적으로 `flush_deferred_dma(now)` 호출해, 현재 시각 이하로 예정된 DMA를 실제 버스 (`Bus.request`)로 재생
  - 재생 시 글로벌 결정성을 위해 `(scheduled_at, issue_order)` 순으로 정렬, 동시간대 충돌은 채널 우선순위(input→output)로 해결
  - DMA 완료 시각을 콜백으로 전달해 compute 파이프라인이 업데이트되도록 `CompletionCallback` 삽입
- 추가 고려사항:
  - CPU fetch/메모리 요청과 충돌 시에도 동일한 `Bus` 인터페이스를 이용하므로, flush가 시뮬레이터 메인 이벤트와 같은 tick에서 실행되어야 함
  - 버스 재생 후에는 VirtualBus 결과와 비교해 겹침이 발생하는지 프로파일링 필요

## DMA 파이프라인 겹침 요구사항
- 입출력 채널을 독립적으로 추적(예: `_dma_available_at_input`, `_dma_available_at_output`)하고, 다음 작업 입력을 미리 발행할 큐·정책이 필요
- DMA 완료를 비동기 이벤트(스케줄러 등록)로 노출해 compute와 전송을 동시에 모델링하고, CPU 루프와의 결정성 유지 규칙을 정의해야 함
- 버스 단일 타임라인을 회피하기 위해 DMA 요청을 이벤트 큐에 기록해 시간순으로 재조립하거나, DMA용 가상 버스 스케줄러를 도입해 실제 버스 호출은 결정된 순서대로만 재생해야 함
- 버스 메트릭을 마스터별·채널별로 확장해 겹침 시나리오에서도 CPU/NPU 경합을 관찰할 수 있도록 하고, 같은 사이클에 여러 DMA가 대기할 때 명시적인 우선순위 규칙을 부여해야 함
- 이러한 변경은 우선 합성 NPU 작업 벤치로 검증한 뒤 실제 프로그램 연동에서 회귀가 없는지 확인해야 함
