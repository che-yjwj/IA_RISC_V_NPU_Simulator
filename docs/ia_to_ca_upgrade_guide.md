# IA → CA 확장 가이드 (Simulink/SoC Blockset 기반)

본 문서는 앞서 정의한 **IA(Instruction-Accurate)** 기반 RISC-V Core / ISA Decoder / NPU Controller / TE·VE·DMA 구조를 **Cycle-Accurate(CA)** 수준으로 확장하는 방법을 단계별로 제시합니다. 목표는 **기능 일치 유지 + 사이클 정확 타이밍** 확보입니다.

---

## 1. 기본 원칙 (IA 대비 CA 차이)
- **시간 해상도**: 고정 샘플타임 `Ts = 1 cycle` 유지, 모든 블록이 동일 클록/리셋에 동기.
- **파이프라인 모델링**: 각 단계(IF/ID/EX/MEM/WB)와 내부 유닛(TE/VE/DMA/AXI/DRAM)의 stage 레지스터 명시화.
- **Hazard/Forwarding/Stall**: 데이터/제어 해저드 탐지, 포워딩 경로, 버블/스톨 삽입.
- **Ready/Valid → Handshake+Credit**: IA의 추상적 busy/done 대신 **사이클 단위 핸드셰이크**와 크레딧/큐 깊이로 흐름 제어.
- **메모리 타이밍**: DRAM 타이밍 파라미터(tRCD/tRP/tRAS/burst) 및 Bank/Row/Col 스케줄링 반영.

---

## 2. 시그널링/클록 도메인
- **클록/리셋 포트 추가**: 모든 Subsystem에 `clk`, `rstn` 입력. Sample time = inherited from clk.
- **동기화 규약**: 한 클록 상승엣지에서 모든 stage 레지스터 동시 업데이트. 비동기 경로 금지.
- **모델 아키텍처**: Top Model에서 Clock Driver → Model Reference 하위 블록들에 전파.

---

## 3. RISC-V Core: IA → CA
### 3.1 파이프라인 단계
- **IF**: PC, IMEM 요청/대기(Instruction Cache/AXI 미스 시 stall)
- **ID**: 디코드/레지스터 읽기/해저드 체크
- **EX**: ALU/FPU, 분기 결정, XNPU custom detect
- **MEM**: 데이터 캐시/AXI 접근, 정렬 예외
- **WB**: Rd 업데이트
> 각 단계 사이에 **Pipeline Register**(Unit Delay) 명확히 배치.

### 3.2 해저드/포워딩
- **RAW 해저드**: ID에서 EX/MEM/WB 대상 레지스터 비교 → 필요 시 stall
- **포워딩**: EX/MEM/WB 결과를 ID/EX 입력으로 MUX 포워딩
- **제어 해저드**: 분기/점프 결정까지의 버블 삽입, BTB/BHT(선택)

### 3.3 XNPU 명령 처리
- custom-0 인식은 **ID/EX 단계**에서 수행, NPU Controller로의 발행은 **Issue Stage** 명시화
- MMIO/CSR 접근은 **MEM 단계**에서 처리(AXI-Lite 사이클 정확)

---

## 4. NPU Controller: IA → CA
### 4.1 큐/ROB 사이클 모델
- IA에서의 추상 Queue → **FIFO(Depth N) + credit 카운터 + 포인터(head/tail)**로 구현
- **Issue Rule**: `deps_ok && resource_free && credit>0`인 사이클에만 1개 발행
- **ROB**: 엔트리별 `(tag, op, start_cycle, done_cycle)` 저장, 완료 이벤트는 유닛에서 사이클 정확 펄스

### 4.2 스케줄러 타이밍
- 한 사이클에 여러 리소스 issue 가능 여부를 파라미터화(`max_issue_per_cycle`)
- 우선순위/라운드로빈 아비터 사이클 정확 구현

---

## 5. TE/VE: 파이프라인 딥 모델
### 5.1 TE(행렬곱/컨볼루션)
- 내부 stage 예: **Load→Align→MAC(S stages)→Reduce→Store**
- 타일 경계 penalty: 첫 타일 warm-up, 마지막 tail 처리를 별도 사이클로 가산
- 데이터폭/포맷별 stage latency 테이블: s8/s16/bf16/fp16/fp32

### 5.2 VE(Elementwise)
- 파이프라인 stage: **Fetch→Op→Write**
- 연속 토큰 처리 시 1/cycle 처리 가능한지(throughput=1) vs k/cycle(슈퍼스칼라) 파라미터화

---

## 6. DMA/AXI/DRAM: 버스·메모리 타이밍
### 6.1 DMA
- **AXI4-Stream/AXI4 Master**로 데이터 전송, burst 길이/align 제약 반영
- 채널 수/우선순위/데이터 폭 파라미터화, credit 기반 백프레셔 구현

### 6.2 AXI Interconnect
- **아비터**(Round-Robin/Priority/Weighted), outstanding transaction 제한, read/write 독립 채널
- 소요 사이클: Address, Data, Response 각 채널의 Ready/Valid 교차로 결정

### 6.3 DRAM Controller (간이 CA)
- Bank/Row/Col 주소 매핑, Row Buffer 히트/미스 판단
- 타이밍 제약: tRCD/tRP/tRAS/tRC, Refresh 주기, Burst length
- 스케줄링: FR-FCFS 우선 (Row-hit 우선), 명령 간 최소 간격 사이클 삽입

---

## 7. SPM(Scratchpad) Bank Conflict (CA)
- Bank 수 = B, 포트 수 = P, 요청은 `(bank_id, addr)`로 인코딩
- **Bank Arbiter FSM**: 같은 bank에 다중 요청 시 1-cycle씩 grant, 나머지 stall
- Dual-port SRAM 옵션: Read/Write 동시 허용 규칙 명세(동일 주소 동시 접근 처리도 규정)

---

## 8. 계측/검증 인프라
- **Cycle Counter**: 전역 사이클, 유닛별 busy/idle/stall 카운터
- **Assertion**: 불법 상태(큐 오버플로, double-issue) 검출
- **Waveform Export**: Signal Logging → VCD/SLX Logging, MATLAB Gantt 변환
- **골든 비교**: IA 결과(명령 시퀀스/완료 순서)와 CA 타임라인 비교

---

## 9. 교정(Calibration) 절차
1) **단일 유닛**(TE/VE/DMA) 마이크로벤치로 latency/throughput 곡선 측정
2) **버스/DRAM**: burst/row-hit/row-miss 케이스별 사이클 측정
3) **통합 경로**: LDMA→MMA→VEC→SDMA 파이프라인, overlap 비율과 stall 원인 분석
4) 파라미터(파이프라인 stage, AXI burst, DRAM timing) 튜닝 후 회귀 테스트

---

## 10. 단계별 마이그레이션 체크리스트
- [ ] 공통 clk/rstn 포트 도입, Sample time 1cycle 일원화  
- [ ] Core 파이프라인(IF/ID/EX/MEM/WB) 분해 + stage 레지스터 삽입  
- [ ] 해저드/포워딩/분기 스톨 로직 추가  
- [ ] NPU Controller: FIFO/ROB를 credit/포인터 기반으로 사이클 모델화  
- [ ] TE/VE: stage 수/throughput 파라미터화, tail penalty 구현  
- [ ] DMA/AXI: Ready/Valid 교차, burst/align/아비터 사이클 반영  
- [ ] DRAM: Bank/Row timing + 스케줄러 + Refresh  
- [ ] SPM Bank Arbiter FSM, dual-port 규칙 구현  
- [ ] 계측/Assertion/Regression 시나리오 세팅  

---

## 11. 예시: Stage 레지스터 템플릿 (Simulink 구현 힌트)
- 각 단계 사이에 `Unit Delay`(Enable 포함)를 두고, **Enable=~stall** 조건으로 버블 생성
- 포워딩은 `Switch/Mux`로 입력 선택, 우선순위는 EX→MEM→WB 순

의사 코드(개념):
```
IF_reg <= (stall_IF) ? IF_reg : {pc_next, instr};
ID_reg <= (stall_ID) ? ID_reg : decode(IF_reg);
EX_reg <= (stall_EX) ? EX_reg : exec(ID_reg, fwd_data);
...
```
- Ready/Valid는 **Valid 비트 파이프라인**을 별도 레지스터 체인으로 전파

---

## 12. SoC Blockset 권장 매핑 (CA 단계)
- **AXI4-Lite**: Core↔NPU MMIO/CSR (사이클 정확 응답 지연 포함)
- **AXI4/Stream**: DMA↔SPM/DRAM 데이터 경로 (Interconnect Arbiter/Outstanding 제약)
- **Memory Controller**: DRAM 타이밍 파라미터와 burst 길이 설정, 채널 수 확장

---

## 13. 산출물/완료 기준 (DoD)
- 단위 유닛: 스펙 대비 latency/throughput 오차 ≤ ±1cycle(마이크로벤치)
- 통합 경로: 파이프라인 overlap/idle 비율 리포트 + stall 원인 분해
- 회귀: IA 타임라인과 기능 일치, CA 계측치는 문서화된 파라미터로 재현 가능

---

## 14. 권장 폴더 구조 (CA 버전)
```
sim/ca/
  core/        # IF/ID/EX/MEM/WB stages, hazards
  npu_ctrl/    # FIFO/ROB cycle model, arbiters
  te/ve/       # pipeline stages, param tables
  dma_axi/     # AXI masters/slaves, interconnect
  dram/        # timing/row-buffer/bank FSM
  spm/         # bank arbiter, sram models
  metrics/     # counters, loggers, assertions
  tests/       # micro, integration, regression
```

---

## 15. 추가 팁
- **Model Reference**로 단계별 컴파일 경량화, **Data Dictionary**로 파라미터 중앙관리
- **Variant Subsystem**: IA/CA 스위치(같은 인터페이스, 내부 구현만 교체)
- **HDL Coder** 경로 고려 시: rate/latency를 정수로 고정, 블로킹 피드백 금지

---

본 가이드는 IA 모델을 **무리 없이** CA로 이행하기 위한 실무 지침입니다. 필요 시 각 유닛(TE/VE/DMA/DRAM/SPM)에 대한 **세부 FSM 다이어그램**과 **테스트 벤치 패턴**을 추가 문서로 확장할 수 있습니다.
