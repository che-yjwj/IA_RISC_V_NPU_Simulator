# Accuracy Guard Metric Definitions

## Fetch Metrics
- `fetch_metrics.latency_p90`: 90th percentile of recorded fetch latencies (cycles). Rounded to two decimal places. Computed from `AdaptiveSimulator._fetch_stats.latency_samples` via `numpy.percentile`.
- `fetch_metrics.latency_p99`: 99th percentile of fetch latencies (cycles). Same rounding and sampling method as `latency_p90`.

## CPU Metrics
- `cpu_metrics.active_cycles`: `max(total_cycles - stall_cycles, 0)`. `total_cycles`는 `SimulationReport.cycles`.
- `cpu_metrics.stall_cycles`: `sum(stall_breakdown.values())`.
- `cpu_metrics.utilization`: `active_cycles / total_cycles` (0 when `total_cycles == 0`).

## Wait Metrics
- `wait_metrics.cpu_total_wait_cycles`: 동일한 스톨 합계 (`cpu_metrics.stall_cycles`).
- `wait_metrics.bus_total_wait_cycles`: 버스 메트릭 `total_wait_cycles`.
- `wait_metrics.bus_avg_wait_cycles`: `avg_wait_cycles` from bus snapshot.
- `wait_metrics.dram_wait_cycles`: DRAM 대기 사이클 (`memory_system.dram_wait_cycles`).
- `wait_metrics.npu_wait_cycles`: 누적 NPU 대기 사이클 (`npu_metrics.wait_cycles`).
- `wait_metrics.npu_avg_wait_cycles`: NPU 작업 평균 대기 사이클 (`npu_metrics.avg_wait_cycles`).
- `wait_metrics.npu_avg_turnaround_cycles`: NPU 작업 평균 완료 시간 (`npu_metrics.avg_turnaround_cycles`).

## NPU Metrics
- `npu_metrics.utilization`: `total_compute_cycles / (sim_time * cores)`. 계산은 `NPUCluster.metrics`에서 수행.
- `npu_metrics.wait_cycles`: NPU 작업이 큐에서 소비한 총 대기 사이클.

## Guard Thresholds
- 기본 설정(`workloads/demos/accuracy_guard/configs/baseline.json`)은 `max_average_deviation=0.05`, `max_single_deviation=0.1`.
- 신규 지표 추가 시 허용 오차를 명시하고 테스트 스위트에 회귀 케이스를 추가해야 한다.
