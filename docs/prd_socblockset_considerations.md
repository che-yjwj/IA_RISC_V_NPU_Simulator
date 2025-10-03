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
