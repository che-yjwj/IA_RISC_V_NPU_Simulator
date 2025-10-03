# RISC-V NPU Simulator PRD - Simulink/SimEvents Block Composition Examples

본 문서는 Hybrid (IA + Timing) 방식의 NPU Simulator를 구현할 때, Simulink와 SimEvents 블록으로 어떤 방식으로 구성할 수 있는지를 예시로 제공합니다.

---

## 1. CPU / Core Subsystem
- **구현 수준**: IA (Instruction Accurate)
- **구성 블록**:
  - Program Counter: Unit Delay
  - Instruction Memory: ROM 블록 (Bus Creator로 InstrBus 생성)
  - Decoder: MATLAB Function (custom-0 → XNPU ISA 명령으로 변환)
  - MMIO: AXI4-Lite Master (SoC Blockset) → NPU Controller와 연결
- **핵심 포인트**: CPU 내부 파이프라인은 단순화, 단지 “명령어 발행기”로만 사용.

---

## 2. ISA Decoder
- **블록 형태**: MATLAB Function
- **입출력**:
  - In: InstrBus (pc, raw, valid)
  - Out: CmdBus (XNPU_Op, rs1, rs2, imm, valid)
- **로직**:
  - opcode==0x0B → XNPU 명령어
  - funct3/funct7로 LDMA, SDMA, MMA, VEC 구분
  - valid 신호로 Ready/Valid 핸드셰이크 구현

---

## 3. NPU Controller
- **블록 형태**: Stateflow (또는 MATLAB Function)
- **내부 상태**:
  - IDLE, ENQUEUE, SCHEDULE, ISSUE, COMPLETE
- **큐 관리**:
  - 명령어 큐: SimEvents Entity Queue
  - ROB(리오더 버퍼): SimEvents Queue + Attribute (start_cycle, done_cycle)
- **리소스 배분**:
  - Resource Pool (TE, VE, DMA 각각)로 SimEvents Resource Manager 사용 가능
  - Arbiter FSM: Round-Robin or Priority (Stateflow로 작성)

---

## 4. Tensor Engine (TE) / Vector Engine (VE)
- **블록 형태**: SimEvents Entity Server (Service Time = Latency)
- **구현 방식**:
  - Service Time = tile_size / throughput + pipeline depth
  - 완료 시 done 신호 출력, busy 상태는 Resource Pool로 갱신
- **Simulink Scope**로 busy/idle 시각화 가능

---

## 5. DMA Engine
- **블록 형태**: SimEvents Entity Server + SoC Blockset AXI4-Stream Source/Sink
- **Service Time**: bytes / BW + base_latency
- **경합 처리**:
  - 다중 DMA 요청은 Arbiter 블록에서 순서 결정
  - AXI Transaction Generator로 traffic pattern 테스트 가능

---

## 6. Scratchpad (SPM)
- **블록 형태**: Multiport RAM + Stateflow FSM
- **Bank Conflict**:
  - 접근 요청에 bank_id 속성 추가
  - Stateflow FSM: 동일 bank 요청 → stall
- **대안**: SimEvents Resource Pool (각 bank를 리소스로 모델링)

---

## 7. DRAM Controller
- **간단 모델**: SimEvents Entity Server (service time = base_latency + size/BW)
- **확장 모델** (선택):
  - Stateflow FSM: tRCD, tRP, tRAS 반영
  - Row Buffer Hit/Miss → 다른 service time 부여
- **SoC Blockset 블록**: Memory Controller 연결 시 realistic한 bus traffic 반영 가능

---

## 8. 계측/성능 분석
- **SimEvents Statistics**:
  - Queue length, Waiting time, Server utilization
- **Simulink To Workspace**:
  - Issue/Start/Done 타임라인 로깅
- **MATLAB Post Processing**:
  - Gantt Chart 생성 (명령 실행 시각화)
  - Stall ratio, Utilization 분석

---

## 9. 전체 연결 예시 (ASCII)
```
[Core] --InstrBus--> [Decoder] --CmdBus--> [NPU Controller]
                                           |   |   |
                                to_TE -----/   |    \----- to_DMA
                                to_VE ---------/
      (MMIO: AXI4-Lite) <-----------------------> Controller CSR
                done/busy ---------------------^

 [TE] [VE] [DMA] : SimEvents Entity Server + busy/done 신호
 [SPM] : Multiport RAM + Bank Arbiter FSM
 [DRAM] : Entity Server or Memory Controller Block
```

---

## 10. 결론
- IA 수준의 CPU와 디코더로 명령어 발행.
- NPU/메모리 자원은 **SimEvents Entity Queue/Server**로 타이밍과 경합 모델링.
- SoC Blockset AXI4/AXI4-Lite 블록을 통해 MMIO와 DMA 트래픽을 현실적으로 반영.
- 성능 분석은 Queue 통계와 Scope/To Workspace 로깅으로 수행.
