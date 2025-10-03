# RISC-V NPU Simulator – Simulink/SimEvents Consolidated PRD

본 문서는 `docs/simulink_docs` 내 기존 분산 문서들을 통합하여 RISC-V + XNPU
시뮬레이터의 요구사항, 설계 가이드, 시뮬레이션 전략, 로드맵을 한 파일로 정리한
버전이다. IA 기반 모델에서 Hybrid(IA+Timing), 동적 스케줄링 확장, CA 단계 이행까지
담아 중복 서술을 제거했다.

---

## 1. 배경 및 목표
- AI 워크로드를 RISC-V 코어와 XNPU 가속기 조합으로 실행하기 위한 시뮬레이터를
  Matlab/Simulink + SimEvents + SoC Blockset으로 구축한다.
- Instruction-Accurate(IA) 수준에서 기능 검증을 확보하고, Timing/Resource Contention을
  반영해 시스템 레벨 성능 최적화를 지원한다.
- ISA 확장(XNPU) 검증, 자원 경합 분석, 동적 스케줄링 실험, FPGA/HIL 확대를 포함한
  로드맵을 제공한다.

---

## 2. 시뮬레이션 수준 비교 및 권장 접근

| 구분 | IA (Instruction-Accurate) | Hybrid (IA + Timing) | CA (Cycle-Accurate) |
|------|----------------------------|----------------------|---------------------|
| 주요 목적 | ISA 기능 검증 | 시스템 레벨 성능/경합 분석 | 미세 타이밍/RTL 검증 |
| CPU 모델 | 파이프라인 추상화, stall 없음 | IA 수준 유지 | IF/ID/EX/MEM/WB + Hazard |
| NPU 모델 | 명령 큐 + 완료 이벤트 | busy_until, latency 모델 | 파이프라인 stage/credit |
| 메모리 | 고정 latency | BW/latency 파라미터, SimEvents Server | tRCD/tRAS, row-buffer FSM |
| 분석 지표 | 기능 일치 | Latency, Util, Stall, Throughput | 절대 cycle, 정확한 타임라인 |
| 속도 | 매우 빠름 | 중간 | 느림 |

> 권장: Hybrid(IA+Timing) 모델을 기본 실험 플랫폼으로 삼고, 필요 시 IA/CA로 전환.

---

## 3. 시스템 아키텍처 개요
- **Top-Level 구성**: RISC-V Core, ISA Decoder, NPU Controller, NPU Subsystem(TE, VE,
  DMA, Scratchpad), DRAM/SoC 인터페이스.
- **큐 및 경합**: 명령 큐(FIFO), ROB(완료 추적), Arbiter FSM, 은행 충돌 모델.
- **XNPU Subsystem**: Tensor Engine(행렬/컨볼루션), Vector Engine(엘리먼트 연산), DMA
  (AXI4-Stream), Scratchpad(SPM) 다중 Bank, DRAM 컨트롤러 연계.
- **SoC Blockset 매핑**:
  - Processor Block 또는 Stateflow 기반 Core ↔ AXI4-Lite MMIO.
  - AXI Interconnect/Arbiter, Memory Controller, AXI Transaction Generator로 실제 인터페이스 모델.
  - DMA는 AXI4-Stream Source/Sink + SimEvents Server로 latency 모델링.

---

## 4. XNPU ISA 및 인터페이스 표면
- **Opcode**: custom-0 (0x0B) 확장. LDMA/SDMA, MMA, VEC, CONF, BARR, PREF 명령군.
- **인코딩**: R형/I형 혼용, funct7/funct3로 세부 동작 구분.
- **Descriptor 구조**:
  - DMA: `src_pa`, `dst_spm`, `bytes`, `stride`, `count`.
  - MMA: `a_spm`, `b_spm`, `c_spm`, `m/n/k`, `lda/ldb/ldc`.
- **CSR/MMIO**: `xnpu_cfg`, `xnpu_stat`, `xnpu_qbase`, `xnpu_qptr`, `xnpu_perf*`, Doorbell,
  Status, Scratchpad window 등.

---

## 5. IA 기준 시뮬레이터 코어
- **파이프라인**: Fetch → Decode → Execute → Mem → Commit (단순 IA 모델).
- **구성 요소**: 레지스터 파일(x0-x31, f0-f31), CSR 집합, 예외 처리(ECALL, Illegal instr,
  page fault 등).
- **메모리 맵**: DRAM, MMIO(NPU), CLINT/PLIC.
- **디코더**: 표준 Opcode + custom-0 → XNPU 명령 판별.
- **XNPU 실행 흐름**: 명령어 큐에 enqueue, 비동기 실행, 완료는 IRQ 또는 폴링으로 감시.

---

## 6. 명령 스트림 생성 및 스케줄링
1. **IR 분석**: 모델 IR에서 NPU 대상 연산(MatMul, Conv, Elementwise 등) 식별 및 속성
   태그(지연 민감, 배치 가능, Throughput 지향)를 부여한다.
2. **타일링 전략**: SPM 용량, DMA burst align, Bank conflict를 고려해 공간/채널/배치 타일
   단위로 분할하고 `Load → Compute → Store` 흐름을 정의한다.
3. **ISA 매핑**: IR 연산을 LDMA/SDMA, MMA, VEC, Barrier 명령으로 변환하고 Descriptor를
   생성한다.
4. **의존성 & 스케줄링**: DFG 토폴로지 정렬, 우선순위 큐, 동적 배칭, Preemption, DMA
   재정렬, Double buffering을 조합한다.
5. **커맨드 큐 포맷**: `[opcode | flags | desc_ptr | dep_token | batch_id | prio]` 구조로 큐와
   Descriptor Pool, Metadata를 동시에 생성한다.
6. **실행 연동**: 결과물은 ELF 섹션(`.npu.cmdq`, `.npu.desc`)과 MMIO/CSR 설정을 통해
   시뮬레이터에 로드된다.

---

## 7. Simulink/SimEvents 구성 가이드
- **CPU/Core Subsystem**: Unit Delay 기반 PC, ROM Instruction Memory, MATLAB Function
  Decoder, AXI4-Lite MMIO. CPU는 명령 발행기 역할에 집중.
- **NPU Controller**: Stateflow FSM(상태: IDLE, ENQUEUE, SCHEDULE, ISSUE, COMPLETE)와
  SimEvents Entity Queue/ROB, Resource Pool과 Arbiter FSM을 사용해 리소스 경합을 모델링.
- **Tensor/Vector Engine**: SimEvents Entity Server로 서비스 시간=타일 지연을 모델.
- **DMA Engine**: SimEvents Entity Server + AXI4-Stream Source/Sink. Burst latency,
  Arbiter 정책(RR, Priority)을 파라미터화.
- **Scratchpad(SPM)**: Multiport RAM + Stateflow Arbiter로 Bank conflict 제어.
- **DRAM Controller**: 간단히는 Entity Server, 확장 시 Stateflow FSM으로 row-hit/row-miss
  타이밍, SoC Blockset Memory Controller와 연동.
- **계측**: SimEvents Statistics(큐 길이, 대기시간, Utilization), Scope/To Workspace 로깅,
  MATLAB Post-processing(Gantt, Stall ratio 분석).

---

## 8. 타이밍 및 경합 모델링 원칙
- Event-Driven(DES) 방식으로 큐/서버/리소스 풀을 구성하면 빠른 탐색과 자원 경합 분석이
  가능하다. Cycle-Accurate는 정밀도가 높지만 속도가 느리므로 필요 시에만 사용한다.
- Metrics: Utilization, Stall ratio, Queue length, DMA overlap ratio, Latency/Throughput.
- SimEvents 없이 구현할 경우 Stateflow + busy_until, MATLAB Function으로 자원 상태를 관리.

---

## 9. 동적 스케줄링 확장 (LLM/MoE/멀티테넌트)
- **목표**: 우선순위, 동적 배칭, 선점, KV cache 관리, MoE 라우팅, DMA/DRAM 재정렬을 통한
  SLA/Throughput 최적화.
- **추가 구조**:
  - High/Low Priority Queue, Dynamic Batch Queue, Preempt Queue.
  - Scheduler FSM(Stateflow)로 큐 선택, 배칭, 선점, 리소스 grant를 처리.
  - TE/VE/DMA를 SimEvents Entity Server, SPM Bank를 Resource Pool로 모델링.
- **주요 정책**:
  - Priority First, WFQ, Deadline 기반 선택.
  - Time-window/Size-threshold 배칭, Shape 호환성 필터.
  - Preemption 시 남은 서비스 시간을 Attribute로 보관하여 재입장.
  - DMA Reorder Buffer, DRAM FR-FCFS vs Round-Robin 비교.
- **KV Cache & MoE**: 페이지 단위 관리, Bank Arbiter, Expert Resource Pool과 SLA 기반
  스케줄링.
- **파라미터/지표**: 배칭 타임아웃, 우선순위 가중치, Preemption quantum, KV page 크기,
  TE/VE/DMA Utilization, Stall breakdown, Fairness(High vs Low latency).
- **Simulink 매핑 표**:

| 기능 | SimEvents 블록 | Stateflow/Simulink | SoC Blockset |
|---|---|---|---|
| High/Low/Batched 큐 | Entity Queue | 큐 선택/배칭 FSM | - |
| Scheduler 정책 | - | Stateflow FSM | - |
| Preemption | Entity Server | Preempt 이벤트 처리 | - |
| Dynamic Batching | Entity Queue | Time-window/Threshold 로직 | - |
| TE/VE | Entity Server | busy/done 신호 | - |
| DMA | Entity Server + Reorder Queue | 순서 정책 | AXI-Stream |
| DRAM | Entity Server | Row-hit/miss 지연 | Memory Controller |
| SPM Bank | Resource Pool | Bank Arbiter FSM | - |

- **체크리스트**: 우선순위 큐 정의, 배칭 파라미터화, Scheduler FSM 구현, DMA/DRAM 정책
  스위치, KV allocator 연동, 메트릭 로깅, SLA 실험 시나리오 확립.

---

## 10. 시스템 레벨 성능 분석 지표
- Latency(P50/P90/P99), Throughput(req/s, tile/s, token/s).
- Utilization(TE/VE/DMA/DRAM), Stall 분해(배칭 대기, Bank conflict, DRAM wait, DMA wait).
- DMA-Compute overlap 비율, Queue length/Wait time 통계, Fairness/QoS 지표.
- 분석 도구: SimEvents Statistics, MATLAB Postproc(Gantt, CDF), Scope/To Workspace 로그.

---

## 11. 개발 로드맵 (Simulink + SoC Blockset)
1. **기본 프레임워크 구축**: IA Core, Decoder, NPU Controller, TE/VE/DMA/SPM/DRAM 블록을
   마련하고 AXI4-Lite MMIO를 연결한다.
2. **자원 경합/지연 모델링**: SimEvents Queue/Server, Resource Pool, Arbiter로 Hybrid 모델을
   완성하고 Utilization/Stall 분석을 가능하게 한다.
3. **ISA & CSR/MMIO 통합**: custom-0 명령, Descriptor, CSR/MMIO, IRQ를 구현한다.
4. **워크로드/계측 환경**: ELF 로더, Micro-benchmark(GEMM/Conv/Vec), SimEvents 통계,
   MATLAB 로그를 구축한다.
5. **성능 분석/파라미터 탐색**: Scratchpad Bank, DMA 채널, DRAM BW, Arbiter 정책 변화에 따른
   성능 곡선을 수집한다.
6. **HW 연계(FPGA/HIL)**: TE/VE를 HDL Coder로 RTL화, FPGA-in-the-loop로 실행하여 모델을
   교정한다.

| 단계 | 목표 | 핵심 도구 | 대표 산출물 |
|------|------|-----------|--------------|
| 1 | IA 구조 확보 | Simulink Subsystem, Stateflow | Core+NPU 기본 모델 |
| 2 | 경합/지연 | SimEvents, SoC Arbiter | Util/Stall 리포트 |
| 3 | ISA 통합 | MATLAB Function, AXI-Lite | 확장 ISA/CSR 모델 |
| 4 | 워크로드 실행 | ELF Loader, AXI TG | 성능 로그/그래프 |
| 5 | 최적화 | Scope, Perf Analyzer | 파라미터-성능 곡선 |
| 6 | HW 연계 | HDL Coder, FPGA HIL | RTL/HIL 데이터 |

---

## 12. 검증 및 테스트 전략
- 단계별 검증: SimEvents 탐색 → Hybrid → Python IA → Cycle-Accurate 모델 전환.
- 테스트:
  - RISC-V arch-test, XNPU 단위(LDMA, SDMA, MMA, VEC, Barrier).
  - 통합: GEMM 타일 파이프라인, DMA↔Compute overlap 시나리오.
  - 예외: Illegal instr, MMIO fault.
- 성능 기준: Latency/Throughput/Utilization, Stall 원인, DMA overlap.
- 회귀: Python IA 결과와 Simulink 모델 간 결과 비교.

---

## 13. IA → CA 확장 가이드 요약
- 공통 클록(1 cycle)과 Reset을 도입하고 모든 블록을 동기화한다.
- RISC-V Core를 IF/ID/EX/MEM/WB Stage로 세분화하고 Hazard/Forwarding/Branch Stall을 구현한다.
- NPU Controller는 FIFO/ROB를 credit/포인터 기반 사이클 모델로 전환하고 issue 규칙을
  `deps_ok && resource_free && credit>0`로 제한한다.
- TE/VE는 파이프라인 stage와 tail penalty를 명시하고 데이터 폭별 latency 테이블을 관리한다.
- DMA/AXI/DRAM은 Ready/Valid 핸드셰이크, burst/align 제약, tRCD/tRP/tRAS/refresh를 반영한다.
- SPM Bank Arbiter FSM을 정확히 구현하고 dual-port 규칙을 정의한다.
- 계측: Cycle counter, busy/idle/stall 카운터, Assertion, Waveform Export.
- 교정 절차: 단일 유닛 → 버스/DRAM → 통합 경로로 단계별 성능을 측정해 파라미터 튜닝.

---

## 14. 워크플로우 및 툴 체인 제안
1. Python IA 시뮬레이터로 명령 시퀀스/디스크립터를 생성.
2. Simulink + SimEvents 모델이 이를 수용하여 Timing/Resource 모델을 적용.
3. SoC Blockset을 통해 AXI 인터페이스, DRAM Controller, FPGA/HIL 연동을 모델링.
4. 결과는 SimEvents 통계 + MATLAB 후처리로 리포트.
5. Variant Subsystem으로 IA/Hybrid/CA를 스위칭하고 Data Dictionary로 파라미터를 중앙관리.

---

## 15. 참고 체크리스트
- [ ] custom-0 ISA, Descriptor, CSR/MMIO 정의 반영
- [ ] SimEvents Queue/Server/Resource Pool 구성 및 Arbiter 정책 파라미터화
- [ ] Dynamic Scheduling 큐/배칭/선점 정책 구현
- [ ] Latency/Utilization/Stall/Fairness 지표 자동 로깅
- [ ] ELF 로더와 워크로드 세트 준비 (GEMM/Conv/Vec, LLM/MoE 시나리오)
- [ ] IA ↔ Hybrid ↔ CA 모델 스위칭 검증
- [ ] FPGA/HIL 경로와 교정 스크립트 확보

---

이 문서는 기존 `prd_*.md`, `riscv_npu_prd_full*.md`, `ia_to_ca_upgrade_guide.md`,
`riscv_npu_simulator_full_combined.md`에 흩어져 있던 내용을 통합/중복 제거한 레퍼런스로,
향후 변경 시 이 파일을 단일 소스로 유지 관리한다.
