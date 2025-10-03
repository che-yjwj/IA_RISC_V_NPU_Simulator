# File: riscv_npu_prd_full.md

# File: prd_system_overview.md

# RISC-V NPU Simulator PRD - System Overview

## 배경
- AI 워크로드는 RISC-V + NPU 구조에서 실행될 필요가 있음.
- 기존 시뮬레이터(gem5, spike)는 범용 CPU 중심 → NPU 확장 필요.

## 시뮬레이션 수준 정의
- IA (Instruction Accurate): 기능 정확성, 사이클 타이밍은 추상화.
- TA (Timing Accurate): 파이프라인/지연 반영.
- CA (Cycle Accurate): RTL 수준 구현.

## SimEvents vs Python 기반
- SimEvents: 이벤트 기반 모델링(Queue/Server) → 아키텍처 탐색 적합.
- Python(IA): RISC-V ISA + NPU 확장명령 실행 검증 적합.

## 목표
- 빠른 아키텍처 탐색 및 성능 병목 분석.
- ISA 확장(XNPU) 검증.
- 자원 경합/지연 모델링.


---

# File: prd_architecture.md

# RISC-V NPU Simulator PRD - Architecture

## Top-level 구조
- RISC-V Core + ISA Decoder + NPU Controller + NPU Subsystem
- NPU Subsystem = Tensor Engine(TE), Vector Engine(VE), DMA, Scratchpad(SPM), DRAM

## 큐 및 경합
- 명령어 큐: FIFO
- 자원 경합: Arbiter FSM
- 지연: 파이프라인 latency + 메모리 타이밍 제약

## 실제 칩 구현
- FIFO (SRAM 기반)
- Arbiter (Round-Robin, Priority)
- Ready/Valid, Flow Control
- DRAM Controller (Row buffer, Timing)

## SimEvents 매핑
- Entity Queue ↔ FIFO SRAM
- Entity Server ↔ Pipeline + FSM
- Resource Pool ↔ Arbiter


---

# File: prd_isa_xnpu.md

# RISC-V NPU Simulator PRD - XNPU ISA

## ISA 확장 (custom-0, opcode=0x0B)
### 명령어 그룹
- LDMA/SDMA: DRAM↔SPM 전송
- MMA: 행렬곱/Conv
- VEC: elementwise
- CONF: 설정
- BARR: 동기화
- PREF: 프리페치

### 인코딩
- R형, I형 혼용
- funct7, funct3로 세분화

### Descriptor 구조체
- DMA: src_pa, dst_spm, bytes, stride, count
- MMA: a_spm, b_spm, c_spm, m,n,k, lda/ldb/ldc

### CSR & MMIO
- CSR: xnpu_cfg, xnpu_stat, xnpu_qbase, xnpu_qptr, xnpu_perf*
- MMIO: doorbell, status, spm window


---

# File: prd_simulator_core.md

# RISC-V NPU Simulator PRD - Simulator Core

## IA 파이프라인
- Fetch → Decode → Execute → Mem → Commit

## 컴포넌트
- 레지스터 파일(x0-x31, f0-f31)
- CSR (mstatus, misa, mtvec, …)
- 예외 처리(ECALL, Illegal instr, page fault)

## 메모리 맵
- DRAM, MMIO(NPU), CLINT/PLIC

## 디코더
- RISC-V 표준 opcode + XNPU(custom-0)

## XNPU 실행(IA)
- 명령어 큐 push, 비차단 실행
- 완료는 IRQ/폴링으로 처리

## 코드 스켈레톤
- Python decode 함수 + exec_xnpu 클래스


---

# File: prd_timing_contention.md

# RISC-V NPU Simulator PRD - Timing & Contention

## SimEvents 모델링
- Entity Queue: 명령어 큐
- Entity Server: TE/VE/DMA/DRAM
- Resource Pool: Arbiter
- Event Calendar: 타임라인 기록

## Cycle-Accurate vs Event-Driven 비교
- Cycle-Accurate: 클럭별 업데이트, stall cycle까지 정밀
- Event-Driven: 이벤트 시점만 업데이트, 빠른 성능 탐색

## SimEvents 없는 경우
- Stateflow + busy_until 구현
- MATLAB Function: 자원 상태 관리

## Metrics
- Utilization, Stall ratio, Queue length, DMA overlap ratio


---

# File: prd_validation_plan.md

# RISC-V NPU Simulator PRD - Validation & Roadmap

## 단계별 로드맵
1) SimEvents 기반 아키텍처 탐색
2) Hybrid (Cycle-aware, Stateflow+Function)
3) IA 시뮬레이터(Py-V)
4) Cycle-Accurate(SystemC/RTL)

## 테스트 전략
- riscv-arch-test
- XNPU 단위: LDMA, SDMA, MMA, VEC, Barrier
- 통합 시나리오: GEMM 타일 파이프라인
- 예외 테스트: Illegal instr, MMIO fault

## 성능 지표
- Latency, Throughput
- Utilization
- DMA-Compute overlap
- Stall cycle 원인 분석


---



---

# File: riscv_npu_prd_full_expanded.md

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



---

# File: prd_socblockset_considerations.md

# RISC-V NPU Simulator PRD - SoC Blockset Considerations

## 1. 목적
- SimEvents 및 Python IA 시뮬레이터만으로는 한계가 있음.
- 실제 SoC 수준의 인터페이스(AXI, DRAM 컨트롤러, Arbiter 등)를 모델링하기 위해 **Simulink SoC Blockset**을 고려.

## 2. 구성 요소 매핑
- **RISC-V Core**: Processor Block 또는 Stateflow 기반 커스텀 코어.
- **NPU Subsystem**
  - Tensor Engine (TE): MATLAB Function, HDL Coder로 RTL화 가능.
  - Vector Engine (VE): MATLAB Function, 파이프라인 latency 설정.
  - DMA Engine: AXI4-Stream Source/Sink + SimEvents Server.
  - Scratchpad (SPM): Multiport RAM, Bank Conflict FSM 추가.
- **메모리 계층**
  - DRAM Controller: SoC Blockset Memory Controller.
  - AXI Interconnect: Arbiter/Router 블록.

## 3. 타이밍/경합 모델링
- Arbiter: SoC Blockset Arbiter 블록 or Stateflow FSM.
- 경합: 여러 마스터가 동시에 접근 시 Arbiter가 grant → 나머지는 stall.
- Latency:
  - TE/VE = 파이프라인 stage latency.
  - DMA/DRAM = Bandwidth/Latency 파라미터화.
  - Bank Conflict = 동일 Bank 접근 시 FSM이 stall 삽입.

## 4. 시뮬레이션 워크플로우
1. Python IA 시뮬레이터 → ISA 디코딩, 명령어 시퀀스 생성.
2. SoC Blockset 모델 → 명령어 스트림을 AXI Transaction으로 변환 후 NPU Subsystem 실행.
3. Co-Simulation → MATLAB/Simulink ↔ Python 연동.
4. 결과 분석 → Scope/To Workspace, MATLAB Gantt Chart.

## 5. 확장 가능성
- FPGA/HIL(Hardware-in-the-Loop): HDL Coder로 TE/VE RTL 변환 → FPGA 연동.
- Cycle-Accurate 이행: SoC Blockset 모델 → RTL-level로 확장 후 Vivado/Quartus 검증.
- 성능 분석: 버스 트래픽, DRAM BW 활용률, 경합 비율.

## 6. 추가 고려사항
- Parameterization: Bank 수, DMA 채널 수, DRAM BW를 Config 블록으로 제어 가능.
- Fault Injection: Illegal access/MMIO 오류를 Stateflow Fault 블록으로 모델링.
- Testbench: riscv-arch-test + Simulink AXI Transaction Generator.

## 7. 결론
- SoC Blockset은 인터페이스 수준(AXI, Arbiter, DRAM 컨트롤러)까지 모델링 가능.
- Python IA와 결합하면 **기능 + 타이밍 + 자원 경합**을 통합적으로 검증 가능.


---

# File: prd_development_roadmap.md

# RISC-V NPU Simulator PRD - Development Roadmap (MATLAB/Simulink 기반)

## 1. 목표
- RISC-V 기반 NPU 시뮬레이터를 MATLAB/Simulink + SoC Blockset 환경에서 개발.
- ISA 수준 정확성(IA) + 자원 경합/지연 모델링을 통합.
- Python은 옵션, Simulink 환경을 메인 개발 플랫폼으로 설정.

---

## 2. 단계별 로드맵

### 단계 1: 기본 프레임워크 구축
- **목표**: IA 수준 RISC-V + NPU 모델링 틀 확보.
- **작업**:
  - Simulink Subsystem으로 RISC-V Core, ISA Decoder, NPU Controller 블록 구성.
  - NPU Subsystem = TE, VE, DMA, Scratchpad(SPM), DRAM.
  - Stateflow FSM으로 명령 발행 및 디스패치 모델링.
- **산출물**: Core + NPU 블록 기본 모델.

### 단계 2: 자원 경합/지연 모델링
- **목표**: Timing + Resource Contention 반영.
- **작업**:
  - SimEvents로 DMA Queue, Command Queue, ROB 구성.
  - Entity Server로 TE/VE latency 모델링.
  - Bank Conflict = Multiport RAM + Stateflow FSM.
- **산출물**: Utilization, Queue Length, Stall ratio, DMA overlap 비율.
- **SoC Blockset 활용**:
  - AXI4-Stream DMA 모델과 Memory Controller 블록 연결.
  - 버스 경합 및 대역폭 제약 반영.

### 단계 3: ISA & CSR/MMIO 통합
- **목표**: RISC-V ISA + XNPU ISA 확장 반영.
- **작업**:
  - ISA Decoder 블록에 custom-0 명령어 해석 추가.
  - CSR/레지스터 파일 구현 (xnpu_cfg, xnpu_stat, xnpu_qbase 등).
  - MMIO 블록 구현 (Doorbell, Status, IRQ).
- **산출물**: ISA/CSR 확장 반영된 Simulink 모델.
- **SoC Blockset 활용**:
  - MMIO = AXI4-Lite Peripheral 블록 매핑.
  - IRQ = Interrupt Controller 블록 연계.

### 단계 4: 시뮬레이션/테스트 환경
- **목표**: 워크로드 실행 및 성능 지표 수집.
- **작업**:
  - ELF 로더 (MATLAB script) → Simulink 메모리 초기화.
  - Micro-benchmark (MatMul tile, Conv tile, Vec 연산) 실행.
  - Scope, To Workspace, Event Calendar로 latency/utilization 기록.
- **산출물**: 워크로드 실행 결과 및 성능 로그.

### 단계 5: 성능 분석 및 최적화
- **목표**: 아키텍처 파라미터 변화에 따른 성능 분석.
- **작업**:
  - Scratchpad 크기/Bank 수 변경 실험.
  - DMA 채널 수, DRAM BW 변화 시 Throughput 비교.
  - TE/VE 파이프라인 깊이 변화 → Stall 비율 분석.
- **SoC Blockset 활용**:
  - Performance Analyzer 블록으로 AXI 버스 활용률 확인.
  - Arbiter 정책 변경 효과(Round-Robin vs Priority) 분석.

### 단계 6: 하드웨어 연계 (FPGA/HIL)
- **목표**: HDL/FPGA 검증으로 모델의 현실성 확보.
- **작업**:
  - TE/VE 블록을 HDL Coder로 RTL 변환.
  - FPGA 보드에서 Hardware-in-the-Loop(HIL) 실행.
  - Simulink 모델과 FPGA 하드웨어 동기화.
- **산출물**: RTL 검증 및 FPGA 성능 데이터.

---

## 3. 요약 로드맵 표

| 단계 | 목표 | 주요 도구 | 산출물 |
|------|------|----------|--------|
| 1 | 기본 구조 | Simulink Subsystem, Stateflow | Core+NPU 블록 |
| 2 | 자원 경합/지연 | SimEvents, SoC Blockset Arbiter | Utilization/Stall 분석 |
| 3 | ISA/CSR/MMIO | MATLAB Function, AXI-Lite | 확장 ISA/CSR 반영 |
| 4 | 테스트 환경 | ELF Loader, AXI Transaction Gen | 워크로드 실행 결과 |
| 5 | 성능 분석 | Scope, Perf Analyzer | 파라미터-성능 곡선 |
| 6 | HW 연계 | HDL Coder, FPGA HIL | RTL 검증, FPGA 성능 |

---

## 4. 결론
- 초기 단계(1~2): Simulink + SimEvents로 기본 구조와 경합 모델.
- 중간 단계(3~4): ISA/CSR 반영 + 워크로드 테스트 환경.
- 최종 단계(5~6): 성능 분석 및 FPGA/HIL 확장.


---

# File: ia_to_ca_upgrade_guide.md

# IA → CA 확장 가이드 (Simulink/SoC Blockset 기반)

본 문서는 앞서 정의한 **IA(Instruction-Accurate)** 기반 RISC-V Core / ISA Decoder / NPU Controller / TE·VE·DMA 구조를 **Cycle-Accurate(CA)** 수준으로 확장하는 방법을 단계별로 제시합니다. 목표는 **기능 일치 유지 + 사이클 정확 타이밍** 확보입니다.

---

## 1. 기본 원칙 (IA 대비 CA 차이)
- **시간 해상도**: 고정 샘플타임 `Ts = 1 cycle` 유지, 모든 블록이 동일 클록/리셋에 동기.
- **파이프라인 모델링**: 각 단계(IF/ID/EX/MEM/WB)와 내부 유닛(TE/VE/DMA/AXI/DRAM)의 stage 레지스터 명시화.
- **Hazard/Forwarding/Stall**: 데이터/제어 해저드 탐지, 포워딩 경로, 버블/스톨 삽입.
- **Ready/Valid → Handshake+Credit**: IA의 추상적 busy/done 대신 **사이클 단위 핸드셰이크**와 크레딧/큐 깊이로 흐름 제어.
- **메모리 타이밍**: DRAM 타이밍 파라미터(tRCD/tRP/tRAS/burst) 및 Bank/Row/Col 스케줄링 반영.

---

## 2. 시그널링/클록 도메인
- **클록/리셋 포트 추가**: 모든 Subsystem에 `clk`, `rstn` 입력. Sample time = inherited from clk.
- **동기화 규약**: 한 클록 상승엣지에서 모든 stage 레지스터 동시 업데이트. 비동기 경로 금지.
- **모델 아키텍처**: Top Model에서 Clock Driver → Model Reference 하위 블록들에 전파.

---

## 3. RISC-V Core: IA → CA
### 3.1 파이프라인 단계
- **IF**: PC, IMEM 요청/대기(Instruction Cache/AXI 미스 시 stall)
- **ID**: 디코드/레지스터 읽기/해저드 체크
- **EX**: ALU/FPU, 분기 결정, XNPU custom detect
- **MEM**: 데이터 캐시/AXI 접근, 정렬 예외
- **WB**: Rd 업데이트
> 각 단계 사이에 **Pipeline Register**(Unit Delay) 명확히 배치.

### 3.2 해저드/포워딩
- **RAW 해저드**: ID에서 EX/MEM/WB 대상 레지스터 비교 → 필요 시 stall
- **포워딩**: EX/MEM/WB 결과를 ID/EX 입력으로 MUX 포워딩
- **제어 해저드**: 분기/점프 결정까지의 버블 삽입, BTB/BHT(선택)

### 3.3 XNPU 명령 처리
- custom-0 인식은 **ID/EX 단계**에서 수행, NPU Controller로의 발행은 **Issue Stage** 명시화
- MMIO/CSR 접근은 **MEM 단계**에서 처리(AXI-Lite 사이클 정확)

---

## 4. NPU Controller: IA → CA
### 4.1 큐/ROB 사이클 모델
- IA에서의 추상 Queue → **FIFO(Depth N) + credit 카운터 + 포인터(head/tail)**로 구현
- **Issue Rule**: `deps_ok && resource_free && credit>0`인 사이클에만 1개 발행
- **ROB**: 엔트리별 `(tag, op, start_cycle, done_cycle)` 저장, 완료 이벤트는 유닛에서 사이클 정확 펄스

### 4.2 스케줄러 타이밍
- 한 사이클에 여러 리소스 issue 가능 여부를 파라미터화(`max_issue_per_cycle`)
- 우선순위/라운드로빈 아비터 사이클 정확 구현

---

## 5. TE/VE: 파이프라인 딥 모델
### 5.1 TE(행렬곱/컨볼루션)
- 내부 stage 예: **Load→Align→MAC(S stages)→Reduce→Store**
- 타일 경계 penalty: 첫 타일 warm-up, 마지막 tail 처리를 별도 사이클로 가산
- 데이터폭/포맷별 stage latency 테이블: s8/s16/bf16/fp16/fp32

### 5.2 VE(Elementwise)
- 파이프라인 stage: **Fetch→Op→Write**
- 연속 토큰 처리 시 1/cycle 처리 가능한지(throughput=1) vs k/cycle(슈퍼스칼라) 파라미터화

---

## 6. DMA/AXI/DRAM: 버스·메모리 타이밍
### 6.1 DMA
- **AXI4-Stream/AXI4 Master**로 데이터 전송, burst 길이/align 제약 반영
- 채널 수/우선순위/데이터 폭 파라미터화, credit 기반 백프레셔 구현

### 6.2 AXI Interconnect
- **아비터**(Round-Robin/Priority/Weighted), outstanding transaction 제한, read/write 독립 채널
- 소요 사이클: Address, Data, Response 각 채널의 Ready/Valid 교차로 결정

### 6.3 DRAM Controller (간이 CA)
- Bank/Row/Col 주소 매핑, Row Buffer 히트/미스 판단
- 타이밍 제약: tRCD/tRP/tRAS/tRC, Refresh 주기, Burst length
- 스케줄링: FR-FCFS 우선 (Row-hit 우선), 명령 간 최소 간격 사이클 삽입

---

## 7. SPM(Scratchpad) Bank Conflict (CA)
- Bank 수 = B, 포트 수 = P, 요청은 `(bank_id, addr)`로 인코딩
- **Bank Arbiter FSM**: 같은 bank에 다중 요청 시 1-cycle씩 grant, 나머지 stall
- Dual-port SRAM 옵션: Read/Write 동시 허용 규칙 명세(동일 주소 동시 접근 처리도 규정)

---

## 8. 계측/검증 인프라
- **Cycle Counter**: 전역 사이클, 유닛별 busy/idle/stall 카운터
- **Assertion**: 불법 상태(큐 오버플로, double-issue) 검출
- **Waveform Export**: Signal Logging → VCD/SLX Logging, MATLAB Gantt 변환
- **골든 비교**: IA 결과(명령 시퀀스/완료 순서)와 CA 타임라인 비교

---

## 9. 교정(Calibration) 절차
1) **단일 유닛**(TE/VE/DMA) 마이크로벤치로 latency/throughput 곡선 측정
2) **버스/DRAM**: burst/row-hit/row-miss 케이스별 사이클 측정
3) **통합 경로**: LDMA→MMA→VEC→SDMA 파이프라인, overlap 비율과 stall 원인 분석
4) 파라미터(파이프라인 stage, AXI burst, DRAM timing) 튜닝 후 회귀 테스트

---

## 10. 단계별 마이그레이션 체크리스트
- [ ] 공통 clk/rstn 포트 도입, Sample time 1cycle 일원화  
- [ ] Core 파이프라인(IF/ID/EX/MEM/WB) 분해 + stage 레지스터 삽입  
- [ ] 해저드/포워딩/분기 스톨 로직 추가  
- [ ] NPU Controller: FIFO/ROB를 credit/포인터 기반으로 사이클 모델화  
- [ ] TE/VE: stage 수/throughput 파라미터화, tail penalty 구현  
- [ ] DMA/AXI: Ready/Valid 교차, burst/align/아비터 사이클 반영  
- [ ] DRAM: Bank/Row timing + 스케줄러 + Refresh  
- [ ] SPM Bank Arbiter FSM, dual-port 규칙 구현  
- [ ] 계측/Assertion/Regression 시나리오 세팅  

---

## 11. 예시: Stage 레지스터 템플릿 (Simulink 구현 힌트)
- 각 단계 사이에 `Unit Delay`(Enable 포함)를 두고, **Enable=~stall** 조건으로 버블 생성
- 포워딩은 `Switch/Mux`로 입력 선택, 우선순위는 EX→MEM→WB 순

의사 코드(개념):
```
IF_reg <= (stall_IF) ? IF_reg : {pc_next, instr};
ID_reg <= (stall_ID) ? ID_reg : decode(IF_reg);
EX_reg <= (stall_EX) ? EX_reg : exec(ID_reg, fwd_data);
...
```
- Ready/Valid는 **Valid 비트 파이프라인**을 별도 레지스터 체인으로 전파

---

## 12. SoC Blockset 권장 매핑 (CA 단계)
- **AXI4-Lite**: Core↔NPU MMIO/CSR (사이클 정확 응답 지연 포함)
- **AXI4/Stream**: DMA↔SPM/DRAM 데이터 경로 (Interconnect Arbiter/Outstanding 제약)
- **Memory Controller**: DRAM 타이밍 파라미터와 burst 길이 설정, 채널 수 확장

---

## 13. 산출물/완료 기준 (DoD)
- 단위 유닛: 스펙 대비 latency/throughput 오차 ≤ ±1cycle(마이크로벤치)
- 통합 경로: 파이프라인 overlap/idle 비율 리포트 + stall 원인 분해
- 회귀: IA 타임라인과 기능 일치, CA 계측치는 문서화된 파라미터로 재현 가능

---

## 14. 권장 폴더 구조 (CA 버전)
```
sim/ca/
  core/        # IF/ID/EX/MEM/WB stages, hazards
  npu_ctrl/    # FIFO/ROB cycle model, arbiters
  te/ve/       # pipeline stages, param tables
  dma_axi/     # AXI masters/slaves, interconnect
  dram/        # timing/row-buffer/bank FSM
  spm/         # bank arbiter, sram models
  metrics/     # counters, loggers, assertions
  tests/       # micro, integration, regression
```

---

## 15. 추가 팁
- **Model Reference**로 단계별 컴파일 경량화, **Data Dictionary**로 파라미터 중앙관리
- **Variant Subsystem**: IA/CA 스위치(같은 인터페이스, 내부 구현만 교체)
- **HDL Coder** 경로 고려 시: rate/latency를 정수로 고정, 블로킹 피드백 금지

---

본 가이드는 IA 모델을 **무리 없이** CA로 이행하기 위한 실무 지침입니다. 필요 시 각 유닛(TE/VE/DMA/DRAM/SPM)에 대한 **세부 FSM 다이어그램**과 **테스트 벤치 패턴**을 추가 문서로 확장할 수 있습니다.


---

# File: prd_system_level_performance_simulator.md

# RISC-V NPU Simulator PRD - System-Level Performance Simulator

## 1. 목표
- CPU의 사이클 정확 모사(CA)는 배제.
- 시스템 레벨에서 **자원 경합, 지연(latency), 활용률(utilization), 스루풋(throughput)**을 분석.
- ISA 기능 검증이 아닌, **성능 최적화**가 주요 목적.

---

## 2. 세 가지 수준 비교

| 구분 | IA (Instruction-Accurate) | Hybrid (IA + Timing) | CA (Cycle-Accurate) |
|------|----------------------------|----------------------|---------------------|
| 목적 | 기능 검증, ISA 확장 확인 | 성능 분석(시스템 레벨) | CPU+NPU 미세 타이밍 분석 |
| CPU 모델 | 단순 실행, stall 없음 | IA 수준(기능만) | 파이프라인/해저드/포워딩 |
| NPU 모델 | 큐/자원 busy 논리만 | busy_until, service time, queue latency | stage 파이프라인, cycle-level FSM |
| DRAM 모델 | 고정 latency | BW/latency param, SimEvents server | tRCD/tRAS/Row-buffer CA |
| 성능 분석 | 불가 | 가능(상대 비교 중심) | 가능(절대 cycle 수치) |
| 속도 | 매우 빠름 | 중간 | 느림 |

---

## 3. 권장 접근법: Hybrid (IA+Timing)

### 3.1 CPU
- IA 수준 유지 (PC 증가, 명령 발행, CSR/MMIO 접근).
- CPU 내부 hazard/포워딩 무시 → 시스템 레벨 성능에 영향 없음.

### 3.2 NPU (TE/VE/DMA)
- 각 유닛에 **latency/busy_until 모델** 삽입.
  - TE: tile size × pipeline depth → 완료 사이클 계산.
  - VE: elementwise latency 모델.
  - DMA: bytes/BW + base_latency.
- NPU Controller는 `resource_free?` 조건을 체크 → issue 지연 발생.

### 3.3 DRAM/SPM
- DRAM: 단순 fixed latency → BW 파라미터 반영, SimEvents Server 모델링 가능.
- SPM: Bank Conflict → 동일 bank 요청 시 대기.

### 3.4 Queue/Dependency
- ROB(리오더 버퍼): start_cycle, done_cycle 기록.
- Dependency Graph 기반 issue 제어.

---

## 4. 계측 지표
- **Latency**: 작업 시작~완료 사이클.
- **Throughput**: ops/sec, tile/sec.
- **Utilization**: TE/VE/DMA busy 비율.
- **Stall 비율**: 큐 대기, bank conflict, DRAM wait.

---

## 5. 활용 방식
- ISA 확장 명령어의 기능은 IA로 확인.
- 시스템 레벨 성능은 Hybrid로 분석.
- CPU 정확 모사 필요 없음 → CPU는 IA만, NPU/메모리만 타이밍 모델링.

---

## 6. 실제 칩과의 괴리
- CPU pipeline: 무시 (성능 분석 목적에 영향 없음).
- 자원 경합/메모리 BW: 반영 → 성능 최적화 목적에는 충분히 수용 가능.
- 절대 cycle 수치보다는 **상대 비교(구조/파라미터 변화)**에 강점.

---

## 7. 결론
- 창훈님의 목적(성능 분석/최적화)에는 **Hybrid (IA+Timing Event-Driven)** 접근이 최적.
- IA 단독은 부족, CA는 과도하게 무겁고 CPU 모사가 불필요.
- Simulink/SimEvents 환경에서 **Entity Queue/Server**를 활용해 DMA/TE/VE/DRAM 경합과 latency를 모델링하면, 실제 칩 대비 수용 가능한 수준의 성능 분석 가능.


---

# File: prd_simulink_simevents_blocks.md

# RISC-V NPU Simulator PRD - Simulink/SimEvents Block Composition Examples

본 문서는 Hybrid (IA + Timing) 방식의 NPU Simulator를 구현할 때, Simulink와 SimEvents 블록으로 어떤 방식으로 구성할 수 있는지를 예시로 제공합니다.

---

## 1. CPU / Core Subsystem
- **구현 수준**: IA (Instruction Accurate)
- **구성 블록**:
  - Program Counter: Unit Delay
  - Instruction Memory: ROM 블록 (Bus Creator로 InstrBus 생성)
  - Decoder: MATLAB Function (custom-0 → XNPU ISA 명령으로 변환)
  - MMIO: AXI4-Lite Master (SoC Blockset) → NPU Controller와 연결
- **핵심 포인트**: CPU 내부 파이프라인은 단순화, 단지 “명령어 발행기”로만 사용.

---

## 2. ISA Decoder
- **블록 형태**: MATLAB Function
- **입출력**:
  - In: InstrBus (pc, raw, valid)
  - Out: CmdBus (XNPU_Op, rs1, rs2, imm, valid)
- **로직**:
  - opcode==0x0B → XNPU 명령어
  - funct3/funct7로 LDMA, SDMA, MMA, VEC 구분
  - valid 신호로 Ready/Valid 핸드셰이크 구현

---

## 3. NPU Controller
- **블록 형태**: Stateflow (또는 MATLAB Function)
- **내부 상태**:
  - IDLE, ENQUEUE, SCHEDULE, ISSUE, COMPLETE
- **큐 관리**:
  - 명령어 큐: SimEvents Entity Queue
  - ROB(리오더 버퍼): SimEvents Queue + Attribute (start_cycle, done_cycle)
- **리소스 배분**:
  - Resource Pool (TE, VE, DMA 각각)로 SimEvents Resource Manager 사용 가능
  - Arbiter FSM: Round-Robin or Priority (Stateflow로 작성)

---

## 4. Tensor Engine (TE) / Vector Engine (VE)
- **블록 형태**: SimEvents Entity Server (Service Time = Latency)
- **구현 방식**:
  - Service Time = tile_size / throughput + pipeline depth
  - 완료 시 done 신호 출력, busy 상태는 Resource Pool로 갱신
- **Simulink Scope**로 busy/idle 시각화 가능

---

## 5. DMA Engine
- **블록 형태**: SimEvents Entity Server + SoC Blockset AXI4-Stream Source/Sink
- **Service Time**: bytes / BW + base_latency
- **경합 처리**:
  - 다중 DMA 요청은 Arbiter 블록에서 순서 결정
  - AXI Transaction Generator로 traffic pattern 테스트 가능

---

## 6. Scratchpad (SPM)
- **블록 형태**: Multiport RAM + Stateflow FSM
- **Bank Conflict**:
  - 접근 요청에 bank_id 속성 추가
  - Stateflow FSM: 동일 bank 요청 → stall
- **대안**: SimEvents Resource Pool (각 bank를 리소스로 모델링)

---

## 7. DRAM Controller
- **간단 모델**: SimEvents Entity Server (service time = base_latency + size/BW)
- **확장 모델** (선택):
  - Stateflow FSM: tRCD, tRP, tRAS 반영
  - Row Buffer Hit/Miss → 다른 service time 부여
- **SoC Blockset 블록**: Memory Controller 연결 시 realistic한 bus traffic 반영 가능

---

## 8. 계측/성능 분석
- **SimEvents Statistics**:
  - Queue length, Waiting time, Server utilization
- **Simulink To Workspace**:
  - Issue/Start/Done 타임라인 로깅
- **MATLAB Post Processing**:
  - Gantt Chart 생성 (명령 실행 시각화)
  - Stall ratio, Utilization 분석

---

## 9. 전체 연결 예시 (ASCII)
```
[Core] --InstrBus--> [Decoder] --CmdBus--> [NPU Controller]
                                           |   |   |
                                to_TE -----/   |    \----- to_DMA
                                to_VE ---------/
      (MMIO: AXI4-Lite) <-----------------------> Controller CSR
                done/busy ---------------------^

 [TE] [VE] [DMA] : SimEvents Entity Server + busy/done 신호
 [SPM] : Multiport RAM + Bank Arbiter FSM
 [DRAM] : Entity Server or Memory Controller Block
```

---

## 10. 결론
- IA 수준의 CPU와 디코더로 명령어 발행.
- NPU/메모리 자원은 **SimEvents Entity Queue/Server**로 타이밍과 경합 모델링.
- SoC Blockset AXI4/AXI4-Lite 블록을 통해 MMIO와 DMA 트래픽을 현실적으로 반영.
- 성능 분석은 Queue 통계와 Scope/To Workspace 로깅으로 수행.


---

# File: prd_system_level_roadmap.md

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


---

