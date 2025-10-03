# RISC-V NPU Simulator - System-Level Development Roadmap (Simulink + SoC Blockset)

## 1. 목표
- CPU 정확 모사(Cycle-Accurate)는 배제, ISA-level IA 모델만 유지.
- 시스템 레벨에서 **자원 경합, 지연, 활용률, 스루풋** 분석을 통한 성능 최적화.
- Simulink + SimEvents + SoC Blockset을 통합 활용.

---

## 2. 단계별 로드맵

### 단계 1: 기본 프레임워크 (IA 수준)
- **목표**: ISA 확장(XNPU 명령) 포함한 기본 구조 확립.
- **구성**:
  - RISC-V Core (IA 수준, PC, InstrBus, MMIO).
  - ISA Decoder (MATLAB Function).
  - NPU Controller (Stateflow FSM).
  - TE/VE/DMA (MATLAB Function, busy_until 기반).
- **SoC Blockset 활용**:
  - Core-MMIO 연결을 AXI4-Lite Master/Slave로 구성.

---

### 단계 2: 자원 경합 및 타이밍 모델링 (Hybrid: IA+Timing)
- **목표**: 자원 경합 및 지연 효과 반영.
- **구성**:
  - SimEvents Entity Queue → 명령 큐, ROB.
  - SimEvents Entity Server → TE/VE/DMA (Service Time=Latency).
  - Resource Pool + Arbiter FSM → 리소스 경합 처리.
- **SoC Blockset 활용**:
  - DMA = AXI4-Stream Source/Sink.
  - DRAM = Memory Controller 블록.
  - Arbiter = AXI Interconnect Arbiter.

---

### 단계 3: ISA/CSR/MMIO 반영
- **목표**: XNPU ISA, CSR, MMIO 구현.
- **구성**:
  - ISA Decoder에 custom-0 명령 매핑.
  - CSR 레지스터(xnpu_cfg, xnpu_stat 등).
  - MMIO + IRQ 신호 처리.
- **SoC Blockset 활용**:
  - CSR/MMIO를 AXI4-Lite Peripheral 블록으로 구현.
  - IRQ → Interrupt Controller 연결.

---

### 단계 4: 워크로드 실행 및 성능 분석
- **목표**: 마이크로벤치마크 기반 성능 분석.
- **구성**:
  - ELF Loader로 메모리 초기화.
  - GEMM 타일, Conv 타일, Vec 연산 실행.
  - SimEvents Statistics: Queue length, Server utilization, Waiting time.
  - MATLAB Post Processing: Gantt Chart, Stall ratio, Utilization 분석.
- **SoC Blockset 활용**:
  - AXI Transaction Generator로 DMA/DRAM 부하 시나리오 생성.
  - Performance Analyzer로 버스/DRAM 활용률 측정.

---

### 단계 5: 아키텍처 파라미터 탐색
- **목표**: 구조적 파라미터 변경 효과 분석.
- **실험 항목**:
  - Scratchpad Bank 수, DMA 채널 수, DRAM BW.
  - TE/VE 파이프라인 깊이, Arbiter 정책.
- **출력**:
  - 파라미터 vs 성능 곡선.
- **SoC Blockset 활용**:
  - Configurable 블록으로 Bank/DMA/Arbiter 정책을 외부 파라미터화.

---

### 단계 6: FPGA/HIL 확장
- **목표**: 실제 하드웨어 기반 검증.
- **구성**:
  - TE/VE 블록을 HDL Coder로 RTL 변환.
  - FPGA 보드에서 Hardware-in-the-loop 실행.
  - Simulink 모델과 FPGA를 동기화.
- **SoC Blockset 활용**:
  - FPGA-in-the-loop 지원 블록.

---

## 3. 요약 로드맵 표

| 단계 | 목표 | 주요 구성 | SoC Blockset 활용 |
|------|------|-----------|-------------------|
| 1 | 기본 구조 | IA Core, Decoder, Controller | AXI4-Lite Core-MMIO |
| 2 | 자원 경합/지연 | SimEvents Queue/Server, Arbiter | AXI-Stream DMA, DRAM Ctrl |
| 3 | ISA/CSR 통합 | XNPU ISA, CSR/MMIO | AXI4-Lite Peripheral, IRQ |
| 4 | 성능 분석 | Micro-benchmarks, Queue Stats | AXI Transaction Gen, Perf Analyzer |
| 5 | 파라미터 탐색 | Bank, DMA, Arbiter 정책 변화 | Configurable SoC 블록 |
| 6 | HW 연계 | FPGA/HIL | HDL Coder, FPGA-in-the-loop |

---

## 4. 결론
- IA 기반 CPU + SimEvents 타이밍 모델로 자원 경합 및 지연 분석 가능.
- SoC Blockset은 **AXI 인터페이스, DRAM Controller, Arbiter**를 사실적으로 모델링하는 핵심.
- 이 로드맵을 따르면 **ISA 검증 + 성능 분석 + 최적화 + HW 연계 검증**까지 단계적으로 구현 가능.
