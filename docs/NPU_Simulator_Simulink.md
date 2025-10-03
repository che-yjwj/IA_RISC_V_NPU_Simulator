#NPU Simulator (Simulink-Only, Extended Edition)
**PRD + 설계 + 확장 기능 (Dynamic Scheduling / IR→CQ 변환 / ISA / Timing)**

---

## 1. 목적 (Objective)
- RISC-V IA 코어를 제거하고, **Simulink/SoC Blockset 기반의 NPU 전용 시뮬레이터**로 단순화.  
- **성능 분석 중심**: 자원 경합, 타일링, 동적 스케줄링, ISA 확장 기능 반영.  
- AI 워크로드(LLM/MoE, KV-cache, Dynamic batching)를 대상으로 **Latency/Throughput/Utilization 최적화 전략** 탐색.  

---

## 2. 요구사항 (Requirements)
- 입력은 **Command Queue (CQ, JSONL)**, CPU 실행·ISA 디코딩 제거.  
- TE/VE/DMA/SPM/DRAM의 **타이밍·자원 경합**을 SimEvents로 모델링.  
- 확장 ISA(xNPU) 기반 LDMA/SDMA/MMA/VEC/CONF/BARR/PREF 지원.  
- **동적 스케줄링** (우선순위, 배칭, 선점, KV-cache 관리, MoE 라우팅).  
- 동일 CQ 입력 → 동일 타임라인 (결정론적 실행).  

---

## 3. 아키텍처 (Simulink-Only)
```
[Command Trace (CQ.jsonl)]
           ↓
  [CQ Loader + Validator]
           ↓
  [NPU Controller (Stateflow FSM)]
       ├── High/Low Priority Q
       ├── Dynamic Batch Q
       └── Scheduler FSM (RR/EDF/Preemptive)
           ↓
     +-------------------+
     |    Resource Pool  |
     +-------------------+
     | TE | VE | DMA | SPM | DRAM |
     +-------------------+
```

---

## 4. 구성 블록 매핑
- **NPU Controller**  
  - Stateflow FSM: ENQUEUE, ISSUE, COMPLETE  
  - 스케줄링: FIFO, Priority, EDF, Dynamic batching, Preemption  

- **Command Queue (CQ)**  
  - Entity Queue (SimEvents)  
  - 속성: `cmd_id, opcode, operands, deps, trace_id`  

- **TE/VE**  
  - Entity Server  
  - Service Time = `tile_size/throughput + pipeline_depth`  

- **DMA**  
  - AXI4-Stream Source/Sink + Entity Server  
  - Service Time = `bytes / BW + base_latency`  

- **SPM (Scratchpad)**  
  - Multiport RAM + Bank Conflict FSM  
  - 동일 bank 접근 시 stall 삽입  

- **DRAM Controller**  
  - SoC Blockset Memory Controller  
  - BW/latency 파라미터 반영  
  - Arbiter로 다중 마스터 충돌 관리  

---

## 5. IR → CQ 변환 (Tiling & Scheduling 포함)
- **타일링 전략**
  - Spatial / Channel / Batch tiling  
  - Load→Compute→Store 단위 CQ 생성  

- **ISA 매핑**
  - MatMul → LDMA + LDMB + MMA + SDMA  
  - Conv → LDMA + MMA/Vec  
  - KV-cache → LDMA_KV / SDMA_KV  
  - MoE → expert_mask 포함 MMA/Vec  

- **스케줄링**
  - Topology Sort 기반 의존성 해소  
  - Prefetch/Barrier 삽입  

---

## 6. ISA 확장 (xNPU)
- **명령어 그룹**
  - LDMA/SDMA: DRAM↔SPM 전송  
  - MMA: 행렬곱/Conv  
  - VEC: elementwise 연산  
  - CONF: 설정  
  - BARR: 동기화  
  - PREF: 프리페치  

- **Descriptor**
  - DMA: `src_pa, dst_spm, bytes, stride, count`  
  - MMA: `a_spm, b_spm, c_spm, m,n,k, lda/ldb/ldc`  

- **CSR/MMIO**
  - CSR: `xnpu_cfg, xnpu_stat, xnpu_qbase, xnpu_qptr, xnpu_perf*`  
  - MMIO: `doorbell, status, spm window`  

---

## 7. Timing & Contention 모델링
- **SimEvents 구조**
  - Entity Queue → 명령어 큐  
  - Entity Server → TE/VE/DMA/DRAM  
  - Resource Pool → Arbiter  
  - Event Calendar → 타임라인 기록  

- **Cycle-Accurate vs Event-Driven**
  - CA: Stall/Hazard까지 반영, 느림  
  - Event-Driven: Latency 추상화, 빠름 (권장)  

- **Metrics**
  - Utilization  
  - Stall Ratio  
  - Queue Length  
  - DMA Overlap Ratio  

---

## 8. 계측 지표 (Metrics)
- **Latency**: 작업 시작~완료  
- **Throughput**: ops/sec, tile/sec  
- **Utilization**: TE/VE/DMA busy 비율  
- **Stall 비율**: Queue wait, SPM conflict, DRAM wait  

---

## 9. 단계별 개발 체크리스트
- [ ] CQ Schema 정의 & Validator  
- [ ] Simulink CQ Loader + Dispatcher  
- [ ] TE/VE/DMA/SPM/DRAM 자원 모델링  
- [ ] Scheduler FSM (FIFO → Priority → EDF → Preemptive 확장)  
- [ ] 타일링 변환기 (IR→CQ)  
- [ ] Golden CQ 워크로드 (GEMM, Conv, Attention, MoE)  
- [ ] Gantt Chart/Timeline CSV Export  
- [ ] CI: Golden Diff + 허용 편차 정책  

---

## 10. 결론
- 본 문서는 **Simulink-Only 기반 NPU 시뮬레이터**에  
  - **Dynamic Scheduling**  
  - **IR→CQ 변환 (타일링 포함)**  
  - **xNPU ISA 확장**  
  - **Timing & Contention 모델링**  
  을 결합한 **최종 확장 설계**.  

- 목표는 CPU 제거 후, **NPU 중심의 성능 최적화 분석 환경**을 완성하는 것.  

