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
