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
