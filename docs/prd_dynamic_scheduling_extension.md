# NPU Simulator – Dynamic Scheduling Extension Guide (Simulink/SimEvents)

본 문서는 Gen AI 워크로드(LLM/MoE/멀티테넌트)를 겨냥해 **동적 스케줄링(dynamic scheduling)** 기능을 시뮬레이터에 확장하는 구체 구현 가이드입니다. Simulink + SimEvents + SoC Blockset을 기준으로 작성되었습니다.

---

## 1. 목표 & 범위
- **목표**: 정적인 FIFO 기반 issue만으로는 어려운 **우선순위, 동적 배칭, 선점, KV cache 관리, MoE 라우팅, DMA/DRAM 재정렬**을 모델링하여 **지연(latency)·스루풋(throughput)·자원활용(utilization)** 최적화 전략을 탐색.
- **범위**: IA 기반 CPU 유지, NPU/메모리 계층에 **Timing+Queueing(DES)**를 추가. 사이클 정확도(CA)는 목표 아님.

---

## 2. 상위 구조 (추가/변경점)
```
[Core(IA)] → [Decoder] → [NPU Controller (Stateflow)]
                                   |      |       |
                         High/Low Prio Q  |   Dynamic Batch Q
                                          |       |
                                  [Scheduler FSM + Policies]
                                   |      |       |
                                   v      v       v
                                  TE     VE      DMA (SimEvents Entity Server)
                                                ↘  DRAM (Entity Server / SoC MC)
SPM (Multi-bank + Bank Arbiter FSM)
```
- **추가 큐**: High/Low priority 큐, Dynamic Batch 큐
- **Scheduler FSM**: 우선순위/선점/배칭/재정렬 정책 적용
- **Resource Pool**: SPM bank, Expert core (MoE) 등

---

## 3. 큐/우선순위/선점

### 3.1 다중 큐 설계
- **HighPrioQ**: Latency 민감 요청(채팅, 실시간 응답)
- **LowPrioQ**: Throughput 지향(batch 처리)
- **BatchQ**: 동적 배칭 후보를 임시 보관

**SimEvents 매핑**
- `Entity Queue` × 2 (High/Low), +1 (Batch)
- 각 엔티티 attribute: `{arrival_ts, deadline, tokens, model_id, session_id}`

### 3.2 Arbiter 정책
- **Priority First**: High → Low
- **WFQ (Weighted Fair Queueing)**: 가중치 w(H), w(L)로 비율
- **Latency First**: `deadline - now` 최소값 우선(Earliest Deadline First 유사)

**Stateflow 구현 팁**
- 매 틱(t): `select_queue()`에서 규칙에 맞는 큐 선택 → `dequeue()` → `issue_or_batch()`

### 3.3 Preemption (선점)
- 긴 작업 실행 중에도 **HighPrio** 도착 시 **context switch** 가능
- **엔티티 상태**: `RUNNING → PAUSED`로 변환, PCB(진행도) 저장

**SimEvents 매핑**
- Server의 서비스 중단: `preempt()`를 모델링하려면 **남은 서비스 시간**을 attribute로 보관 후 **PAUSED Queue**에 재입장

---

## 4. Dynamic Batching

### 4.1 정책
- **Time-window**: 배칭 타임아웃(예: 2ms) 내 들어온 요청 묶기
- **Size-threshold**: N개 이상 모이면 즉시 발행
- **Shape-compatibility**: 같은 dtype/shape group만 묶기 (또는 패딩 허용)

### 4.2 효과 모델링
- 배칭 크기 B → **큰 matmul**로 TE 호출 → **service time 감소(연산 효율↑), 대기 지연 증가**의 trade-off
- 시뮬레이터에서 **B vs latency/throughput** 곡선 측정

**SimEvents 매핑**
- `BatchQ`에 같은 group의 엔티티를 accumulate → 타임아웃 또는 임계치 만족 시 합쳐서 하나의 **배치 엔티티**로 발행(속성에 `batch_size=B` 저장)
- TE Server의 `service_time = f(B, tile, dtype)`

---

## 5. KV Cache / 메모리 관리

### 5.1 페이지화 & 배치
- KV cache를 **페이지 단위**로 관리 (SPM/DRAM bank에 매핑)
- **할당 정책**: First-fit / Best-fit / Buddy / Paged-Attention 유사 정책

### 5.2 충돌 모델링
- 동일 bank 과다 접근 → Bank Arbiter에서 stall
- DRAM bank/row 충돌 시 **추가 대기** 모델

**SimEvents & Stateflow 매핑**
- KV alloc/free를 Stateflow Manager로 구현, alloc 실패 시 **spill**(DRAM) 이벤트 생성
- Bank Arbiter FSM이 **동일 bank 다중 요청** 시 1-cycle(or service quanta)씩 round-robin

---

## 6. MoE 라우팅

### 6.1 Expert 선택
- 토큰/배치별 expert k개 선택 (확률/토크나이저에 기반한 패턴 입력 가능)
- 코어/클러스터에 **Expert Pool**로 할당

**SimEvents 매핑**
- Expert 별 **Resource Pool**(capacity=코어 수) 정의
- **자원 부족 시 대기** → QoS에 따라 preemption/우선순위 재조정

---

## 7. DMA/DRAM 동적 스케줄링

### 7.1 DMA 재정렬
- 전송 순서를 DRAM 행정렬/연속성 기준으로 **reorder**하여 **burst 효율** 극대화
- 우선순위에 따라 **젤 급한 전송 먼저**

### 7.2 DRAM 정책
- **FR-FCFS(Row-hit 우선)** vs **Round-Robin** 비교
- Refresh 이벤트 삽입(간단 모형)

**SimEvents 매핑**
- DMA: Server 앞단에 `Reorder Buffer (Queue)` 추가 → `compare()` 규칙으로 pop 순서 결정
- DRAM: Hit/Miss에 따른 `service_time` 차등 + 주기적 refresh로 **busy slot** 삽입

---

## 8. Scheduler FSM (상세)

### 8.1 상태
- `IDLE` → `PICK` → `BATCH_ACCUM` → `ISSUE` → `MONITOR` → `PREEMPT`

### 8.2 의사코드
```text
loop each tick:
  update_metrics()
  if high_prio_nonempty(): q = HIGH
  elif need_batch(): q = BATCH
  else: q = LOW

  task = peek(q)
  if should_batch(task): accumulate_to_batch(task); continue

  if preempt_needed(task): preempt_running_lower_prio()

  if resource_available(task): issue(task)
  else: hold(task)

  on_event(done/preempt/arrival): update_queues()
```

---

## 9. 파라미터 & 실험 설계

### 9.1 핵심 파라미터
- 배칭: `batch_timeout(ms)`, `batch_min_size`, `shape_grouping`
- 우선순위: `prio_weights`, `latency_sla(ms)`
- 선점: `preempt_enable`, `quantum(ms)`
- 메모리: `KV_page_size`, `SPM_bank`, `DRAM_BW`
- DMA: `burst_len`, `reorder_enable`

### 9.2 성능 지표
- P50/P90/P99 **Latency**, **Throughput**(req/s, tok/s)
- **Utilization**: TE/VE/DMA/DRAM busy%
- **Stall/Wait 분해**: 배칭 대기, bank conflict, DRAM wait, DMA wait
- **Fairness/QoS**: High vs Low 요청의 latency gap

---

## 10. Simulink/SimEvents/SoC Blockset 매핑 표

| 기능 | SimEvents 블록 | Stateflow/Simulink | SoC Blockset |
|---|---|---|---|
| High/Low/Batched 큐 | Entity Queue(3개) | Queue 선택 로직 | - |
| 스케줄러 정책 | - | Stateflow FSM | - |
| Preemption | Entity Server(잔여시간 attr) | Preempt 이벤트 처리 | - |
| Dynamic Batching | BatchQ(Entity Queue) | 타임아웃/임계치 로직 | - |
| TE/VE | Entity Server | busy/done 신호 | - |
| DMA | Entity Server + ReorderQ | burst/순서 정책 | AXI-Stream |
| DRAM | Entity Server | Row-hit/miss 서비스타임 | Memory Controller |
| SPM Bank | Resource Pool | Bank Arbiter FSM | - |

---

## 11. 로깅/분석 툴체인
- SimEvents Statistics (queue length, wait, util)
- Simulink Scope / To Workspace (issue/start/done 타임라인)
- MATLAB Postproc: Gantt Chart, CDF/Percentile 그래프

---

## 12. 리스크/주의점
- 배칭 타임아웃이 너무 크면 P99 latency 악화
- Preemption 과다 사용 시 컨텍스트 스위치 오버헤드 증가
- MoE 라우팅이 불균형하면 특정 코어 과부하 → backpressure 필요
- DRAM reorder는 fairness를 저해할 수 있음 → SLA/우선순위와 균형

---

## 13. 체크리스트
- [ ] High/Low/Batched 큐 생성 및 attribute 정의
- [ ] 배칭 타임아웃/임계치 파라미터화
- [ ] Scheduler FSM에 우선순위/선점/배칭 규칙 구현
- [ ] DMA ReorderQ/DRAM 정책 스위치 추가
- [ ] KV cache allocator/Bank Arbiter 연동
- [ ] 메트릭 로깅/리포트 스크립트 완성
- [ ] 실험 시나리오(P50~P99, SLA 위반율) 표준화

---

## 14. 확장: 멀티테넌트 & SLA
- 테넌트별 큐/가중치, admission control(큐 길이 임계치 넘으면 거부/지연)
- SLA 모드: `latency-first`/`throughput-first` 스위치

---

본 가이드는 **실제 서비스 수준의 동적 스케줄링 현상을 시뮬레이터에 반영**하기 위한 실무 지침입니다. 필요한 경우, 각 정책별 **Stateflow 차트 템플릿**과 **SimEvents 파라미터 세트(.m 초기화 스크립트)**를 추가 제공할 수 있습니다.
