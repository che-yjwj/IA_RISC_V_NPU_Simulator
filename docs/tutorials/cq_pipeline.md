# CQ Pipeline Tutorial

CQ(Command Queue) 입력을 구성하고 `run-cq` 경로를 통해 ELF 실행 결과와 비교하는 절차입니다.

## 1. 준비
- CQ 스키마: `specs/cq.adaptation.yaml`
- 어댑터 사양: `docs/cq_adaptation_spec.md`
- 실험용 설정: `ia_risc_v_npu/workloads/demos/cq/` (필요 시 새로 작성)

## 2. CQ 계획 생성
```bash
python -m src.cq.tools.plan_generator \
  --isa specs/isa.yaml \
  --input workloads/demos/cq/sample_plan.yaml \
  --output /tmp/sample_plan.jsonl
```
*(도구가 아직 없다면, Stage 6에서 제공될 스크립트를 작성해 위 경로를 갱신하세요.)*

## 3. CQ 실행
```bash
python -m src.simulator.cli run-cq \
  --trace /tmp/sample_plan.jsonl \
  --config ia_risc_v_npu/workloads/calibration/configs/rr_baseline.json \
  --output /tmp/cq_summary.json
```

## 4. ELF 결과와 비교
```bash
python -m src.simulator.cli benchmark \
  --instructions 1000 \
  --config ia_risc_v_npu/workloads/calibration/configs/rr_baseline.json \
  --output /tmp/elf_summary.json

python -m scripts.cq_vs_elf_benchmark \
  --cq /tmp/cq_summary.json \
  --elf /tmp/elf_summary.json \
  --json
```

## 5. 편차 분석
- `docs/tutorials/accuracy_guard_troubleshooting.md`를 참고해 `cq_summary.json`에서 주요 지표를 점검합니다.
- CQ 경로가 ±15% 범위를 벗어나면 스케줄링·메모리 파라미터를 조정해 다시 측정하세요.

## 6. 확장 아이디어
- Stage 6에서 WFQ/EDF 정책을 CQ 경로와 조합해 비교 실험을 진행합니다.
- 노트북(`notebooks/cq_vs_elf_analysis.ipynb`)에 결과를 로드해 시각화하면 추세를 빠르게 파악할 수 있습니다.
