큐 기반 DES  하이브리드 구조 PRD

## 1. 목적

- NPU 시뮬레이터에서 명령어 발행, 메모리 접근, 레지스터 관리 기능을 큐 기반으로 모델링하고,
- DES(이산 사건 시뮬레이션)을 결합하여 타이밍 정밀도를 보장한다.
- 목표는 파이프라인 병목, 리소스 경합, 데이터 의존성을 정밀하게 시뮬레이션하는 것이다.

## 2. 주요 컴포넌트

- **Instruction Queue**: CPU/Frontend에서 발행한 명령어를 버퍼링
- **Memory Access Queue**: DMA/Load-Store 요청 관리 및 DRAM ↔ Scratchpad 전송
- **Register Queue**: 연산자 Operand 준비 상태 관리
- **DES Event Kernel**: 이벤트 스케줄링 및 글로벌 타임 관리

## 3. 데이터 흐름 (ASCII 다이어그램)

```
CPU/Frontend → Instruction Queue → Dispatch → Memory Access Queue ↔ DRAM/SRAM
                                                 ↓
                                          Register Queue
                                                 ↓
                                         Tensor/Vector Engine

```

## 4. 시뮬레이션 고려사항

| 큐 종류 | Blocking Mode | Non-Blocking Mode | 모델링 포인트 |
| --- | --- | --- | --- |
| Instruction Queue | Dependent inst. stall | Independent inst. 실행 | Dispatch 정책 (in-order, OOO) |
| Memory Access Queue | Memory ready 전 stall | Prefetch / double buffering | Bus contention, bank conflict |
| Register Queue | Operand 준비 대기 | Ready inst. 먼저 실행 | Scoreboard, Tomasulo-like 모델 |

## 5. 큐 vs DES 비교

| 구분 | 큐 기반 | DES 기반 |
| --- | --- | --- |
| 직관성 | 높음 (FIFO 모델) | 낮음 (이벤트 스케줄링) |
| 하드웨어 친화성 | 실제 Queue 구조와 유사 | 이벤트 엔진 기반 |
| 타이밍 정확도 | 중간 (사이클 단위) | 높음 (사이클/이벤트 단위) |
| 구현 난이도 | 낮음 | 높음 |
| 성능(시뮬 속도) | 빠름 | 느림 |
| 확장성 | 제한적 | 이벤트 정의로 확장 용이 |

## 6. 결론

- **큐 기반**: 구조적 병목 및 자원 경합을 직관적으로 모델링.
- **DES 기반**: 타이밍과 이벤트를 정밀하게 모델링.
- **하이브리드**: 큐는 “무엇이 대기 중인가”, DES는 “언제 일어나는가”를 담당 → 직관성과 정밀성을 동시에 확보.
