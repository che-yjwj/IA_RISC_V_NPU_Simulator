# Two-Layer CNN Demo

이 데모는 `tests/integration/test_multilayer_cnn.py`에서 사용하는 2계층 CNN 시나리오에 맞춘 하드웨어 프로필을 제공합니다.

## Files

- `configs/integration.json` – 통합 테스트와 동일한 텐서 크기를 대상으로 한 기준 하드웨어 구성. L1/L2 캐시, 버스, DRAM, NPU 정책을 경량 설정으로 조정했습니다.

## Usage

### Pytest 통합 테스트

```bash
python3 -m pytest tests/integration/test_multilayer_cnn.py -q \
    --cnn-payload-scale 0.05 \
    --maxfail=1
```

테스트는 자동으로 `integration.json`을 기준으로 작성된 시나리오와 동일한 텐서 크기를 로드하며, 픽스처가 `resource` 모듈을 활용해 단계별 피크 RSS를 `record_property`로 남깁니다.

### CLI 벤치마크 예시

```bash
python3 -m src.simulator.cli benchmark --instructions 20000 \
    --config workloads/demos/cnn/configs/integration.json \
    --output /tmp/cnn-benchmark.json
```

위 명령은 통합 테스트와 동일한 캐시·메모리·NPU 파라미터로 합성 프로그램을 실행해 MIPS와 메모리 통계를 수집합니다. OOM 위험이 있는 큰 텐서를 실험할 때는 `integration.json`을 복사해 캐시 크기와 NPU 코어 수를 조정한 뒤 테스트나 벤치마크에 전달하면 됩니다.
