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
