# Benchmark & CI Automation Tutorial

벤치마크 명령과 정확도 가드를 CI 파이프라인에 통합하는 절차입니다.

## 1. 로컬 스크립트 실행
```bash
python -m src.simulator.cli benchmark \
  --instructions 1000 \
  --config ia_risc_v_npu/workloads/calibration/configs/rr_baseline.json \
  --output /tmp/ci_smoke.json

python -m src.simulator.cli benchmark \
  --instructions 1 \
  --config ia_risc_v_npu/workloads/demos/accuracy_guard/configs/baseline.json \
  --output /tmp/accuracy_ci.json
```

## 2. 체크 스크립트 작성 예
```bash
python - <<'PY'
import json
from pathlib import Path

def check(path, key):
    data = json.loads(Path(path).read_text())
    value = data.get(key)
    print(f"{path}: {key}={value}")

check('/tmp/ci_smoke.json', 'mips')
check('/tmp/accuracy_ci.json', 'accuracy_guard')
PY
```

## 3. GitHub Actions 워크플로 예시
`.github/workflows/ci_benchmark.yml` (예시)
```yaml
- name: Run short benchmark
  run: |
    python -m src.simulator.cli benchmark \
      --instructions 1000 \
      --config ia_risc_v_npu/workloads/calibration/configs/rr_baseline.json

- name: Accuracy guard check
  run: |
    python -m src.simulator.cli benchmark \
      --instructions 1 \
      --config ia_risc_v_npu/workloads/demos/accuracy_guard/configs/baseline.json
```

## 4. 성능 회귀 감지
- `docs/validation_calibration.md`의 벤치마크 절차를 주기적으로 실행하여 baseline MIPS와 비교합니다.
- 결과를 `performance_results.json`에 누적하고, 차이가 특정 임계값(예: ±5%)을 넘으면 실패하도록 스크립트를 확장하세요.

## 5. 문서·도구 연동
- 설정 관리: `docs/config_parameter_management.md`
- 정확도 가드 분석: `docs/tutorials/accuracy_guard_troubleshooting.md`
- 스케줄러 비교: `docs/tutorials/scheduler_basics.md`
