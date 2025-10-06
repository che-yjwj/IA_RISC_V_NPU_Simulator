# 정확도 가드 지표 확장 가이드

## 개요
Stage 5 리팩토링 단계에서 정확도 가드가 추적하는 핵심 지표를 확장했다. 기존 사이클·미스 레이트 중심의 검증을 유지하면서 다음 항목을 추가로 캡처하여 CPU/NPU 자원 점유와 대기 거동을 정량화한다.

## 새로 추가된 지표
- `fetch_metrics.latency_p90`, `fetch_metrics.latency_p99`: 명령 페치 지연의 90/99 분위수. 퍼센트는 2자리까지 반올림된다.
  - 분위수 계산은 최대 4096개의 표본을 대상으로 한 reservoir sampling 기반 근사치이다.
- `cpu_metrics.*`: 활성/스톨 사이클을 기반으로 계산된 CPU 활용도(`utilization`)와 누적 스톨 사이클(`stall_cycles`).
- `wait_metrics.*`: CPU, 버스, DRAM, NPU 대기 지표를 한눈에 보이도록 집계한 사전. 각 항목은 절대 사이클 수 또는 평균값이다.
- `npu_metrics.utilization`, `npu_metrics.wait_cycles`, `npu_metrics.avg_wait_cycles`: NPU 클러스터의 점유율과 대기 통계. 기존 히스토리에서 계산하던 값을 골든 비교 항목으로 승격했다.

## 골든 JSON 유지 방법
1. `python -m src.simulator.cli benchmark --instructions 1 --config workloads/demos/accuracy_guard/configs/baseline.json --output /tmp/accuracy_summary.json`
2. `accuracy_guard.status`가 `ok`인지 확인한 뒤 `/tmp/accuracy_summary.json`에서 필요한 항목을 골든 파일에 반영한다.
3. 새 지표가 추가될 때마다 골든에 해당 키를 명시적으로 포함해야 정확도 가드가 회귀를 감지할 수 있다.

## 테스트 커버리지
- `tests/unit/test_accuracy_guard.py`에 대기 지표 편차를 검증하는 테스트를 추가하여 중첩 딕셔너리 키가 올바르게 평탄화되는지 확인했다.
- `workloads/demos/accuracy_guard/configs/golden_summary.json`을 갱신하여 배포 예제가 최신 지표를 사용하도록 맞췄다.

## 추후 권장 사항
- 워크로드별 골든에 선택적 지표 세트를 정의하고, 중요한 지표(예: `cpu_metrics.utilization`)는 공통 스키마로 관리하는 것을 권장한다.
- 퍼센트 계산 또는 분위수 정의가 변경될 수 있으므로, 변경 시 문서와 테스트를 동시에 업데이트한다.
