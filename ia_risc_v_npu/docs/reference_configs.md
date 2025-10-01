# Baseline Simulator Configurations

다음 표는 시뮬레이터에 포함된 대표 하드웨어 설정 JSON 파일과 용도를 요약합니다. 새로운 실험을 시작할 때에는 가장 가까운 베이스라인을 복사해 수정하고, 수정한 설정을 워크로드 디렉터리의 `configs/` 하위에 배치하세요.

| 시나리오 | 경로 | 설명 |
| --- | --- | --- |
| 2계층 CNN 통합 테스트 | `workloads/demos/cnn/configs/integration.json` | `tests/integration/test_multilayer_cnn.py`에서 사용하는 축소된 캐시·버스·DRAM·NPU 파라미터. CI 메모리 한도를 넘지 않도록 텐서 크기와 버스 대역폭을 조정했습니다. |
| Accuracy Guard 스모크 | `workloads/demos/accuracy_guard/configs/baseline.json` | 정확도 가드를 활성화하고 `configs/golden_summary.json`을 기준으로 편차를 검사하는 최소 구성. `benchmark --instructions 1`과 함께 사용해 가드 통과/실패 흐름을 빠르게 재현합니다. |
| 이벤트 버스 프로파일링 | `workloads/profiling/configs/event_bus_baseline.json` | 버스/이벤트 스케줄러 병목을 분석하기 위한 기준 구성. DMA 겹침 실험과 CLI 벤치마크 스모크 테스트(`--instructions 5000`)에 사용합니다. |

## 사용 지침

1. 구성 파일은 모두 `schema_version` 필드로 현재 유효한 스키마를 선언합니다. 스키마가 변경되면 `src.simulator.config.validate_simulator_config`가 검증 오류를 발생시킵니다.
2. `determinism` 블록이 존재할 경우, 시뮬레이터가 구성 로드를 마치기 전에 RNG 시드와 BLAS 스레드를 고정합니다. 멀티쓰레드 의존성이 있는 워크로드에서는 필수적으로 설정하세요.
3. 새 시나리오를 추가할 때에는 `workloads/<scenario>/configs/` 디렉터리를 만들고, README에 해당 구성의 용도와 권장 커맨드를 문서화합니다.

향후 NPU/버스 종합 벤치마크나 DRAM 타이밍 실험이 추가되면 이 문서를 업데이트해 공용 베이스라인을 계속 정렬하세요.
