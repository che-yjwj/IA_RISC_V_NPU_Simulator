# Basic Smoke Test Tutorial

시뮬레이터가 정상 동작하는지 빠르게 확인하기 위한 절차입니다.

## 1. 의존성 설치
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ia_risc_v_npu[dev]
```

## 2. 짧은 벤치마크 실행
```bash
python -m src.simulator.cli benchmark \
  --instructions 1000 \
  --config ia_risc_v_npu/workloads/calibration/configs/rr_baseline.json \
  --output /tmp/smoke_summary.json
```

- 실행 시간이 짧아 CI 사전 점검용으로 적합합니다.
- 설정 파일은 accuracy guard가 비활성화되어 있어 순수 성능만 측정합니다.

## 3. 핵심 지표 확인
```bash
jq '. | {cycles, instructions_executed, mips}' /tmp/smoke_summary.json
```

- `mips` 값이 0에 가깝다면 워크로드가 너무 짧은 것이므로 `--instructions` 값을 늘려 확인합니다.

## 4. 오류 발생 시
- `python -m scripts.check_specs_index` 같은 유지 보수 스크립트로 문서 일관성도 함께 점검하세요.
- 정확도 검증이 필요한 경우 `docs/tutorials/accuracy_guard_troubleshooting.md`를 참고하세요.
