# Profiling Utilities

`workloads/profiling` 디렉터리는 버스와 이벤트 스케줄러 동작을 분석하기 위한 합성 워크로드와 도구를 제공합니다.

## Baseline Hardware Config

- `configs/event_bus_baseline.json` – 버스 경합과 DMA 겹침을 재현하기 위한 기준 하드웨어 구성입니다. CLI 벤치마크나 커스텀 실험을 시작할 때 이 파일을 복사해 파라미터를 조정하세요.

### CLI Smoke Benchmark

```bash
python3 -m src.simulator.cli benchmark \
  --instructions 5000 \
  --config ia_risc_v_npu/workloads/profiling/configs/event_bus_baseline.json \
  --output /tmp/event-bus-baseline.json
```

## Deep-Dive Profiling Script

`event_bus_profile.py`는 합성 CNN/NPU 시나리오를 실행해 버스 요청, 이벤트 큐, 가상 DMA 재생 결과를 JSON으로 출력합니다. 필요 시 위의 기준 구성을 참조해 하드웨어 값을 조정하고, 결과는 아래와 같이 캡처합니다.

```bash
python3 workloads/profiling/event_bus_profile.py \
  > workloads/profiling/event_bus_profile.json
```

출력 JSON에는 CNN 및 NPU DMA 요청 타임라인, 버스 메트릭, 큐 깊이 통계가 포함됩니다. 추가 시나리오를 추가할 때에는 `workloads/<scenario>/configs/` 구조를 재사용하고, README에 구성 파일과 사용 예시를 문서화하세요.
