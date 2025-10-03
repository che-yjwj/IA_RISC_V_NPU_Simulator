# RISC-V NPU Simulator PRD (Expanded Edition)

---

## 1. System Overview (Expanded)
- 배경: RISC-V + NPU 기반 AI 워크로드 가속 필요.
- 시뮬레이터 수준: IA 중심, 추후 TA/CA 확장 가능.
- **Simulink + SoC Blockset 적용시 장점**
  - AXI4, AXI4-Lite, AXI-Stream 같은 실제 인터페이스 블록 모델링 가능.
  - 프로세서 블록(RISC-V)와 메모리 컨트롤러 블록을 시각적으로 연결 가능.
  - DMA/DRAM 모델을 그대로 가져다 쓰며, 자원 경합·대역폭 제한을 구성 가능.
- Python IA 시뮬레이터와 Co-Simulation: ISA-level 실행은 Python, 타이밍/자원 경합은 SimEvents/SoC Blockset.

---

## 2. Architecture (Expanded)
- **Top-level**: RISC-V Core, ISA Decoder, NPU Controller, NPU Subsystem
- **NPU Subsystem**: TE, VE, DMA, Scratchpad(SPM), DRAM
- **실제 칩 자원 경합**
  - FIFO → 하드웨어 SRAM 큐
  - Arbiter FSM → 라운드로빈/우선순위
  - Ready/Valid 기반 흐름 제어
- **SoC Blockset 매핑**
  - Processor Block → RISC-V Core
  - AXI Interconnect Block → TE/VE/DMA와 SPM/DRAM 연결
  - Memory Controller Block → DRAM Controller
  - Custom Subsystem → NPU (MATLAB Function 블록 기반)

---

## 3. ISA & XNPU Extensions (Expanded)
- **ISA 확장 (custom-0, 0x0B)**
  - LDMA, SDMA, MMA, VEC, CONF, BARR, PREF
- **Descriptor 구조체**
  - DMA: src_pa, dst_spm, bytes, stride, count
  - MMA: a_spm, b_spm, c_spm, m,n,k, lda/ldb/ldc
- **CSR 정의**
  - xnpu_cfg, xnpu_stat, xnpu_qbase, xnpu_qptr, xnpu_perf*
- **MMIO**
  - Doorbell, Status, Error 레지스터
- **SoC Blockset 적용**
  - MMIO 영역 → AXI-Lite Register 블록 매핑

---

## 4. Simulator Core (IA, Expanded)
- **IA 파이프라인**
  - Fetch → Decode → Execute → Mem → Commit
- **구현**
  - ELF 로더, 레지스터 파일, CSR, 예외 처리
- **XNPU 실행**
  - 명령어 큐 push, 비차단 실행
  - 완료는 IRQ/폴링으로 확인
- **Python 기반 IA 예시 코드**
  - decode() 함수, exec_xnpu() 클래스
- **SoC Blockset 연동**
  - IA Simulator에서 NPU 호출 → HDL Coder Wrapper 블록으로 전달 가능

---

## 5. Timing & Contention (Expanded)
- **SimEvents**
  - Entity Queue = FIFO Queue
  - Entity Server = TE/VE/DMA/DRAM
  - Resource Pool = Arbiter
- **Cycle-Accurate vs Event-Driven**
  - Cycle-Accurate: Stall, Hazard까지 반영 (느림)
  - Event-Driven: Latency 추상화, 빠른 탐색
- **SoC Blockset 적용**
  - DMA = AXI-Stream 기반 Entity Server
  - DRAM = Memory Controller 블록
  - Arbiter = AXI Arbiter 블록
- **Metrics**
  - Utilization, Stall ratio, DMA overlap ratio

---

## 6. Validation & Roadmap (Expanded)
- **단계별**
  1. SimEvents 기반 아키텍처 탐색
  2. Hybrid Cycle-aware(Stateflow+Function)
  3. IA(Py-V) 시뮬레이터
  4. Cycle-Accurate(SystemC/RTL)
- **테스트 전략**
  - riscv-arch-test
  - XNPU 단위: LDMA, MMA, VEC
  - 통합: GEMM tile 파이프라인
  - 예외: Illegal instr, MMIO fault
- **SoC Blockset Testbench**
  - AXI Transaction Generator → DMA/DRAM 검증
  - Scope로 latency/utilization 확인
- **Regression**
  - Python IA 결과 ↔ Simulink/SoC Blockset 결과 비교
  - RTL/FPGA HIL 검증으로 확장

---

## 7. 결론
- IA 시뮬레이터는 **ISA 확장 검증**에 필수.
- SimEvents/SoC Blockset은 **자원 경합·인터페이스 검증**에 강점.
- 최종 로드맵: Python IA → SimEvents/SoC Blockset 하이브리드 → SystemC/RTL.

