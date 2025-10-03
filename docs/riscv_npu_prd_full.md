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

