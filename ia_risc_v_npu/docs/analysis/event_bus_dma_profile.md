# Event Scheduler & Bus Profiling Summary

## Profiling setup
- Script: `workloads/profiling/event_bus_profile.py` (outputs JSON report to `workloads/profiling/event_bus_profile.json`)
- Workloads: three CNN kernels generated via `workloads.cnn_workload.generate_cnn_workload`
- Simulator entry point: `src/simulator/main.py:158` (`AdaptiveSimulator.run_simulation`)
- Metrics tapped:
  - Event queue instrumentation through `ProfilingEventScheduler`
  - Bus metrics and request traces from `src/simulator/memory.py:223`

## Event scheduler observations
- Queue depth remained `1` across all workloads (17/217/163 events respectively)
- Scheduled callbacks exclusively `execute_instruction_event`, confirming a single-cycle instruction pump (`src/simulator/main.py:170`)
- Histogram shows no simultaneous events at identical timestamps; batching would not reduce heap operations in current flows
- Max queue depth equaled the minimum event delay guard (`MIN_EVENT_DELAY = 1`), highlighting absence of overlapping callbacks

## Bus usage observations (CPU 시나리오)
- CPU 마스터(`0`)만 버스를 사용했고, CNN 워크로드별로 전송 요청은 2/14/11회(총 128/896/704바이트)로 집계
- 평균 대기 사이클 `0`, 최대 큐 깊이 `1`이며 슬라이스 기반 전송 지연은 `Bus._calculate_transfer_cycles` (`src/simulator/memory.py:389`)와 일치
- 큐가 늘어나지 않아 페치가 완전히 직렬화된 현재 파이프라인에서는 배치 최적화 이점이 없음

## NPU DMA 프로파일링
- `ClusterTask` 3개를 `issue_at` 0/40/80에 제출했지만, 버스 전역 시각(`Bus.now`)이 출력 DMA 시각으로 진전되면서 후속 입력 DMA가 동일 시각(예: 137/291)으로 밀려 직렬 실행됨 (`src/npu/cluster.py:101-134`)
- 관측 타임라인: `task_0` 입력 0→17, 연산 17→137, 출력 137→154; `task_1` 입력 154→171, 연산 171→291, 출력 291→308; `task_2` 입력 308→325, 연산 325→445, 출력 445→462
- 채널 분리 후 버스 통계는 `avg_queue_depth = 1.33`, `avg_wait_cycles = 5.67`로 상승했고 큐 깊이가 2까지 늘어나 출발 시점 겹침을 감지했으나, 실질적 겹침(연산과 다음 입력/출력 동시 진행)은 아직 실현되지 않음
- 현 구현은 `_dma_available_at`을 채널별로 분리했으나 버스가 단일 타임라인을 사용해 요청 순서를 고정하기 때문에, 실제 겹침을 위해서는 이벤트 기반 DMA 완료 처리 또는 사전 스케줄링으로 요청 순서를 재배치할 추가 작업이 필요함

## CPU+NPU 버스 경합 실험
- Synthetic 시나리오: 마스터 0(CPU) 요청 6회(64B씩)와 NPU DMA 작업 3개(입력/출력 128~256B)를 동일 버스에서 스케줄링(`workloads/profiling/event_bus_profile.py:112`)
- 결과: 버스 평균 대기 4.33 사이클, 최대 큐 깊이 3으로 CPU와 NPU 요청이 동시에 대기함을 확인 (`ia_risc_v_npu/workloads/profiling/event_bus_profile.json:400`)
- CPU 요청 가운데 일부가 DMA 완료에 밀려 `grant_at`이 `request_at`보다 뒤로 이동하며 실제 대기 시간을 관찰 (`ia_risc_v_npu/workloads/profiling/event_bus_profile.json:360`)
- NPU 출력 DMA는 여전히 연속적으로 후속 입력 DMA를 지연시키므로, CPU 경합 환경에서도 DMA 겹침이 제한됨

## Virtual DMA 스케줄러 실험
- VirtualBus 프로토타입(`workloads/profiling/event_bus_profile.py:33`)은 `bus.now` 의존성을 제거해 입력 DMA 요청이 본래 이슈 시각(예: 40, 171 사이클)에 기록되도록 함 (`ia_risc_v_npu/workloads/profiling/event_bus_profile.json:512`)
- 그러나 버스 자체가 단일 자원으로 순차 처리되므로 grant 시각은 여전히 154/308 사이클에 고정되고 대기 시간이 크게 증가 → 시간 재생만으로는 겹침이 보장되지 않음을 확인
- 입력 프리페치를 실현하려면 다중 작업을 동시에 큐잉하고, 이벤트 기반 DMA 완료를 처리해 compute가 진행되는 동안 후속 입력을 발행할 수 있는 스케줄링 계층이 필요
- VirtualBus 스케줄을 실제 `Bus`에 재생(replay)한 결과, 예상한 타이밍(0/137/154/291/308/445 사이클)을 그대로 유지하면서도 대기 시간은 0으로 수렴 (`ia_risc_v_npu/workloads/profiling/event_bus_profile.json:590`). 즉, 재생 계층이 정확히 타임라인을 보존하면 기존 버스와의 충돌 없이 동작 가능함을 확인

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
