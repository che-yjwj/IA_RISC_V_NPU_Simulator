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
