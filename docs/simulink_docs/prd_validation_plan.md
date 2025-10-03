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
