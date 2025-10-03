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
