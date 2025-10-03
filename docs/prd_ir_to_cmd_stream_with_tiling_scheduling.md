# PRD: IR → Command Queue Stream 변환 (타일링 + 스케줄링 포함)

## 1. 개요
- IR(Intermediate Representation)은 모델 연산을 하드웨어 독립적으로 표현한 중간 표현이다.  
- 이를 기반으로 **ISA 명령어 + 디스크립터 기반의 커맨드 큐 스트림**을 생성해야 실제 NPU 또는 시뮬레이터에서 실행할 수 있다.  
- 변환 과정은 단순 연산 매핑을 넘어서 **타일링(Tiling)**과 **스케줄링(Scheduling)**까지 고려해야 한다.  

---

## 2. 단계별 절차

### 2.1 IR 연산 식별 및 분류
- IR 그래프에서 NPU 대상 연산(MatMul, Conv2D, Reduce, Elementwise, Copy 등)을 식별.  
- 각 연산에 실행 속성 태그 부여:  
  - Latency-sensitive  
  - Throughput-oriented  
  - Batchable 여부  

---

### 2.2 타일링(Tiling) 전략
- 대규모 연산을 NPU 하드웨어 제약(SPM 용량, Bank conflict, DMA burst alignment)에 맞춰 **타일 단위**로 분할.  
- 타일링 유형:  
  - **Spatial tiling** (공간 분할)  
  - **Channel tiling** (채널 분할)  
  - **Batch tiling** (배치 크기 분할)  
- 각 타일은 `Load → Compute → Store` 실행 단위로 변환된다.  

---

### 2.3 명령 매핑 및 ISA 연관성
- IR 연산 → NPU ISA 명령으로 변환:  
  - MatMul → LDMA + LDMB + MMA + SDMA  
  - Conv → LDMA + MMA/Vec  
  - KV-cache → LDMA_KV / SDMA_KV  
  - MoE → expert_mask 포함한 MMA/Vec  
- ISA 포맷 필드(opcode, funct3, funct7, imm 등)에 맞게 디스크립터 생성.  
- 제어 명령(Barrier, CSR/MMIO 세팅, IRQ/doorbell)을 큐에 삽입.  

---

### 2.4 데이터 의존성 & 스케줄링
- **의존성 해소**: IR SSA/DFG 분석 → 토폴로지 정렬.  
- **스케줄링 정책**:  
  - 우선순위 큐(Priority Queue: High vs Low)  
  - Dynamic Batching (동일 shape 요청을 타임윈도우 내 묶기)  
  - Preemption (긴 요청 중 긴급 요청 들어오면 context switch)  
  - DMA Reordering (burst 효율 최대화, DRAM row-hit 우선)  
- **Double buffering**: Load(k+1) ↔ Compute(k) ↔ Store(k-1) 오버랩.  
- **Token 기반 동기화**: dep_token을 desc.flags에 삽입하여 Wait/BARR 구현.  

---

### 2.5 커맨드 큐 스트림 생성
- 커맨드 엔트리 포맷 예시:  
  ```
  [opcode | flags | desc_ptr | dep_token | batch_id | prio]
  ```
- 엔트리 메타데이터:  
  - `batch_id`: Dynamic batching 그룹 ID  
  - `prio`: High/Low 요청 구분  
  - `dep_token`: 실행 의존성 제어  
  - `expert_mask`: MoE에서 활성화할 core cluster  
- 최적화 기법: DMA burst alignment, SPM bank conflict 회피, 배치 크기 trade-off 조정.  

---

### 2.6 출력 및 인터페이스 연동
- 산출물:  
  - **Command Queue**: 실행 명령 스트림  
  - **Descriptor Pool**: DMA, MMA, Vec 파라미터 블록  
  - **Metadata**: trace_id, batch_id, dep_token, prio  
- 연동:  
  - ELF 섹션(`.npu.cmdq`, `.npu.desc`)에 매핑  
  - MMIO/CSR(`xnpu_cfg`, `xnpu_qbase`, `doorbell`) 설정  
  - IRQ/Status CSR로 완료 여부 모니터링  

---

## 3. ISA 연관성
- ISA 명령 포맷에 정확히 부합해야 HW/시뮬레이터가 직접 해석 가능.  
- 스케줄링 속성(`prio`, `batch_id`, `dep_token`)은 ISA 확장 필드/flags로 매핑.  
- CSR/MMIO/IRQ 명령은 IR 단계에서 태깅 후 큐에 포함.  

---

## 4. 종합 예시: MatMul (Tiling + Scheduling 반영)

### IR 연산
```
C[M×N] = A[M×K] × B[K×N]
```

### 타일링
- 타일 크기: M=128, N=128, K=64  
- 총 타일 수: (M/128) × (N/128) × (K/64)  

### 커맨드 스트림 예시
```
[LDMA, srcA, spmA, len, stride, prio=H, batch_id=1]
[LDMA, srcB, spmB, len, stride, prio=H, batch_id=1]
[MMA, spmA, spmB, spmC, M=128, N=128, K=64, dep_token=AB_ready, prio=H]
[SDMA, spmC, dstC, len, stride, batch_id=1, irq=1]
```

---

## 5. 결론
- IR → Command Stream 변환은 단순 연산 매핑이 아니라, **타일링과 스케줄링**까지 함께 고려해야 한다.  
- 우선순위, 동적 배칭, Preemption, DMA Reordering 같은 요소가 반영되어야 실제 NPU 런타임 동작 및 성능 추이를 현실적으로 모사할 수 있다.  
- 시뮬레이터 구현 시 IR 변환 모듈과 스케줄러 모듈을 분리하여 유지보수성과 실험 확장성을 확보하는 것이 바람직하다.  
