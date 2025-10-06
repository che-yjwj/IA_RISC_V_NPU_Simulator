# Accuracy Guard Troubleshooting Tutorial

정확도 가드가 `failed` 또는 `error` 상태를 반환했을 때 문제 원인을 파악하고 대응하는 절차입니다.

## 1. 실패 재현
```bash
python -m src.simulator.cli benchmark \
  --instructions 1 \
  --config ia_risc_v_npu/workloads/demos/accuracy_guard/configs/baseline.json \
  --output /tmp/accuracy_summary.json
```

- 종료 코드가 1이면 정확도 가드가 실패한 것입니다.

## 2. 편차 큰 지표 찾기
```bash
jq '.accuracy_guard.metrics[] | select(.deviation != null and .deviation > 0.05)' \
  /tmp/accuracy_summary.json
```

- `deviation` 또는 `infinite_deviation` 필드를 확인하여 어떤 지표가 골든과 어긋났는지 파악합니다.

## 3. 골든과 비교
```bash
python - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path('/tmp/accuracy_summary.json').read_text())
golden = json.loads(Path('ia_risc_v_npu/workloads/demos/accuracy_guard/configs/golden_summary.json').read_text())

for name, metrics in summary.get('accuracy_guard', {}).items():
    pass
for metric in summary['accuracy_guard']['metrics']:
    if metric['deviation'] and metric['deviation'] > 0.05:
        print(metric['name'], metric['expected'], metric['actual'], metric['deviation'])
PY
```

## 4. 골든 재생성 (의도된 변경 시)
```bash
python -m scripts.regenerate_accuracy_golden --instructions 1
```

- 재생성 직후 `git diff`로 변화량을 검토하고 커밋 메시지에 편차 사유를 기록합니다.

## 5. CI 통합
- `.github/workflows/specs_check.yml`처럼 정확도 가드 전용 워크플로를 추가할 수 있습니다.
- 복수의 워크로드를 점검하려면 `docs/validation_calibration.md`의 검증 루프를 참고하세요.

## 6. 추가 팁
- 스케줄 정책을 바꾼 후 정확도 가드가 실패하면 `docs/tutorials/scheduler_basics.md`로 정책별 지표를 먼저 비교합니다.
- DRAM/버스 파라미터 변경 후에는 `docs/validation_calibration.md`에 정리된 벤치마크를 함께 수행하여 부작용을 조기에 발견합니다.
