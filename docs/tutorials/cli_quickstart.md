# CLI Quickstart Tutorial

이 튜토리얼은 RISC-V NPU 시뮬레이터를 처음 실행하는 사용자를 위한 빠른 안내서입니다.

## 1. 환경 준비
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ia_risc_v_npu[dev]
```

## 2. ELF 워크로드 실행
```bash
python -m src.simulator.cli simulate \
  build/program.elf \
  --config ia_risc_v_npu/workloads/demos/accuracy_guard/configs/baseline.json \
  --output /tmp/sim_summary.json
```

- `build/program.elf` 위치는 사용자가 준비한 RISC-V ELF 바이너리로 교체합니다.
- `--config` 옵션은 accuracy guard 설정을 활성화합니다.
- `--output` JSON에는 사이클, MIPS, 메모리/버스/NPU 메트릭이 포함됩니다.

## 3. 결과 확인
```bash
jq '. | {cycles, mips, miss_rates, npu_metrics}' /tmp/sim_summary.json
```
- `miss_rates`는 L1/L2/ICache 미스율을 보여줍니다.
- `npu_metrics.utilization`으로 NPU 점유율을 확인합니다.

## 4. 정확도 가드 상태 점검
```bash
jq '.accuracy_guard.status' /tmp/sim_summary.json
```
- `"ok"`가 아니면 골든과 편차가 발생한 것이니 `docs/accuracy_guard_metrics.md`를 참고해 원인을 분석하세요.

## 5. 다음 단계
- 벤치마크 측정을 위해 `python -m src.simulator.cli benchmark --instructions 1000`을 실행해 보세요.
- NPU 스케줄 정책 비교는 `docs/tutorials/scheduler_basics.md`에서 이어집니다.
