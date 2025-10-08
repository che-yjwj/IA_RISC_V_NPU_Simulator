# CQ Pipeline Tutorial

CQ(Command Queue) 입력을 구성하고 `run-cq` 경로를 통해 ELF 실행 결과와 비교하는 절차입니다.

## 1. 준비
- CQ 스키마: `specs/cq.adaptation.yaml`
- 어댑터 사양: `docs/cq_adaptation_spec.md`
- 실험용 설정: `workloads/cq/`

## 2. CQ 계획 생성
```bash
python -m src.cq.tools.plan_generator \
  --isa specs/isa.yaml \
  --input workloads/cq/sample_gemm.yaml \
  --output /tmp/sample_plan.jsonl
```

## 3. CQ 실행

`run-cq` CLI 명령어는 `CQDispatcher`를 활용하여 커맨드 큐(CQ)를 처리하고 시뮬레이션 결과를 생성합니다. 이 방식은 `AdaptiveSimulator.run_cq_trace`와 동일한 디스패처 기반 실행 파이프라인을 공유하며, DMA, 버스, TE(Tensor Engine), SPM(Scratchpad Memory) 등 자원 모델을 효율적으로 관리합니다. CLI 출력의 `dispatch` 및 `execution` 섹션은 디스패처가 기록한 큐 대기 시간과 자원 사용 통계를 상세하게 반영합니다.

```bash
python -m src.simulator.cli run-cq \
  --trace /tmp/sample_plan.jsonl \
  --config ia_risc_v_npu/workloads/calibration/configs/rr_baseline.json \
  --output /tmp/cq_summary.json
```

> 디스패처 경로 안내: `run-cq`는 `CQDispatcher`를 통해 명령을 순회하며,
> 동일한 자원 모델(DMA/Bus/TE/SPM)을 사용하는 `AdaptiveSimulator.run_cq_trace`
> 호출과 동일한 실행 파이프라인을 공유합니다. CLI 출력의 `dispatch` 및
> `execution` 섹션은 dispatcher가 기록한 큐 대기시간과 자원 사용 통계를
> 반영합니다.

### 3.1 실행 단계 흐름
1. `load_cq_trace`가 JSONL을 파싱해 `CommandQueue`를 생성합니다.
2. `build_execution_plan`이 ISA 명세 기반으로 DMA/GEMM/FENCE 액션을 정리합니다.
3. `CQDispatcher.run`이 큐를 순회하며 의존성 검증, 큐 대기시간 기록, 실행 콜백을 호출합니다.
4. 실행 콜백은 `AdaptiveSimulator`의 DMA/TE 핸들러에 위임해 버스/클러스터 자원을 스케줄링합니다.
5. dispatcher가 완료/실패 상태를 갱신하고, 통계(`dispatch`, `execution`)를 CLI 요약에 담아 반환합니다.

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

Dispatcher 통계를 함께 확인하려면 `--show-dispatch` 플래그를 추가하세요. 인간
친화적 출력에 queue wait, DMA 사이클, 실행 횟수가 포함됩니다.

```bash
python -m scripts.cq_vs_elf_benchmark \
  --cq workloads/cq/sample_gemm.jsonl \
  --show-dispatch
```

`compare_cq_vs_elf` 스텁 역시 내부적으로 `AdaptiveSimulator.run_cq_trace`
경로를 사용하므로, dispatcher 기반 CQ 실행과 동일한 스케줄링 결과를
비교 보고서에 포함합니다.

> 참고: CQ vs ELF 비교 보고서의 `cq_summary.dispatch` 필드는 CLI 출력과 동일한
> dispatcher 통계를 담고 있으며, `cq_summary.execution`은 DMA/GEMM 수행 횟수와
> 예측된 사이클 합계를 제공합니다. 동일한 CQ 입력을 CLI와 스크립트에서
> 실행하면 두 경로의 통계가 일치해야 합니다.

### 4.1 보고서 해석 팁
- `cq_summary.dispatch.executed` / `rejected`: dispatcher가 실제로 스케줄링한
  명령 수와 실패한 명령 리스트를 확인할 수 있습니다. 실패가 발생하면 ISA
  명세나 의존성 규칙을 먼저 점검하세요.
- `cq_summary.execution.count`: DMA/GEMM/FENCE 실행 횟수로, ISA→CQ 변환과
  자원 모델 설정이 기대한 파이프라인을 만들었는지 빠르게 검증할 수 있습니다.
- `cq_summary.execution.dma_bytes`, `dma_cycles`: 동일 워크로드를 반복 실행해
  자원 모델 파라미터(버스 대역폭, DMA 패널티 등)의 영향을 비교할 때 활용합니다.
- ELF 경로(`elf_summary`)가 `status: ok`인 경우 `cq_summary`와 `elf_summary`
  사이의 오차율을 계산해 Stage 7의 ±15% 기준을 검토할 수 있습니다.

## 5. 편차 분석
- `docs/tutorials/accuracy_guard_troubleshooting.md`를 참고해 `cq_summary.json`에서 주요 지표를 점검합니다.
- CQ 경로가 ±15% 범위를 벗어나면 스케줄링·메모리 파라미터를 조정해 다시 측정하세요.

## 6. 확장 아이디어
- Stage 6에서 WFQ/EDF 정책을 CQ 경로와 조합해 비교 실험을 진행합니다.
- 노트북(`notebooks/cq_vs_elf_analysis.ipynb`)에 결과를 로드해 시각화하면 추세를 빠르게 파악할 수 있습니다.
