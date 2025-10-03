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
