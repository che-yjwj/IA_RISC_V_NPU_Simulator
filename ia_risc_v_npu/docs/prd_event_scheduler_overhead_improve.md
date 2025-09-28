heduler`는 Python의 heapq와 dataclass 객체를 사용하여 고빈도 이벤트 처리에서 오버헤드가 발생합니다. [1](https://www.notion.so/27b6cc566b0b80d99a6decc320178e78?pvs=21)  스케줄링 오버헤드를 줄이기 위한 방법:

1. **이벤트 배치 처리**: 동일한 타임스탬프의 여러 이벤트를 단일 힙 연산으로 처리
2. **데이터 구조 최적화**: 현재 dataclass 기반 `_ScheduledEvent`를 경량 튜플이나 NumPy 배열로 대체
3. **이벤트 풀링**: 객체 풀링을 구현하여 빈번한 이벤트 생성/소멸로 인한 가비지 컬렉션 오버헤드 감소

## Python 언어 제약 완화

프로젝트는 12-20 MIPS 성능을 목표로 하면서 Python 성능 제약에 직면하고 있습니다. [2](https://www.notion.so/27b6cc566b0b80d99a6decc320178e78?pvs=21)  주요 최적화 전략:

1. **Numba JIT 컴파일**: 핵심 이벤트 스케줄링 및 처리 함수, 특히 힙 연산과 콜백 실행에 Numba 데코레이터 적용
2. **NumPy 벡터화**: DMA 슬라이스 연산 등에서 가능한 경우 NumPy 배열을 사용한 대량 이벤트 처리
3. **Cython 확장**: 핵심 성능 경로를 위해 EventScheduler 코어를 Cython으로 변환 고려
4. **결정적 환경 최적화**: 코드베이스에서 이미 구현된 결정적 실행 제어를 활용 [3](https://www.notion.so/27b6cc566b0b80d99a6decc320178e78?pvs=21)

## 메모리 시스템 이벤트 복잡도 감소

계획된 메모리 시스템은 버스 중재, DRAM 뱅킹, 캐시 연산으로 상당한 이벤트 복잡도를 생성할 예정입니다. [4](https://www.notion.so/27b6cc566b0b80d99a6decc320178e78?pvs=21)  최적화 접근법:

1. **이벤트 병합**: 여러 작은 메모리 연산을 더 큰 트랜잭션으로 결합하여 이벤트 수 감소
2. **슬라이스 기반 처리**: 정확도와 성능의 균형을 위해 구성 가능한 세분화로 계획된 슬라이스 기반 버스 전송 구현 [5](https://www.notion.so/27b6cc566b0b80d99a6decc320178e78?pvs=21)
3. **지연 이벤트 생성**: 정확도 요구사항이 필요할 때만 상세한 타이밍 이벤트 생성
4. **메모리 접근 예측**: 자주 접근하는 메모리 타이밍 패턴을 캐시하여 반복적인 이벤트 체인 생성 방지

## NPU 클러스터 DMA 이벤트 최적화

NPU 클러스터는 DMA 연산을 슬라이스 기반 이벤트 체인으로 구현할 예정입니다. [6](https://www.notion.so/27b6cc566b0b80d99a6decc320178e78?pvs=21)  성능 개선 방법:

1. **DMA 전송 집계**: 가능한 경우 여러 작은 DMA 전송을 더 큰 연산으로 배치
2. **파이프라인 겹침 모델링**: 과도한 중간 이벤트 생성 없이 입출력 DMA와 컴퓨트 연산의 파이프라이닝을 효율적으로 모델링
3. **적응형 DMA 슬라이싱**: 전송 크기와 시스템 부하에 따라 `dma_slice_bytes`를 동적으로 조정하여 이벤트 세분화 최적화
4. **코어 스케줄링 최적화**: 최소한의 이벤트 오버헤드로 효율적인 코어 선택 알고리즘(min_finish_time, round-robin) 구현

## 구현 전략

프로젝트의 단계별 마이그레이션 접근법을 따라: [7](https://www.notion.so/27b6cc566b0b80d99a6decc320178e78?pvs=21)

1. **Phase 2-3**: 슬라이스 기반 처리로 버스 및 DRAM 이벤트 생성 최적화
2. **Phase 4**: 캐시 이벤트 병합 및 지연 생성 구현
3. **Phase 6**: NPU 클러스터 구현 중 DMA 최적화 기법 적용
4. **Phase 8**: 프로파일링 및 언어 수준 최적화(Numba/Cython) 적용

## 성능 모니터링

초기 8-12 MIPS 목표에서 12-15 MIPS로 최적화하는 프로젝트 목표에 맞춘 성능 추적을 구현하세요. [8](https://www.notion.so/27b6cc566b0b80d99a6decc320178e78?pvs=21)  기존 벤치마크 인프라를 사용하여 이벤트 처리 처리량을 측정하고 남은 병목지점을 식별하세요.

## Notes

코드베이스는 현재 이벤트 기반 마이그레이션의 Phase 1 단계로, 기본 EventScheduler는 구현되었지만 복잡한 메모리 및 NPU 시스템은 아직 계획 단계입니다. 권장사항은 현재 Python 성능 제약을 해결하면서 증가할 이벤트 복잡도에 대비하는 데 중점을 둡니다. 최적화 노력 전반에 걸쳐 프로젝트의 결정적 실행 요구사항을 유지해야 합니다.

Wiki pages you might want to explore:

- [RISC-V Engine (che-yjwj/IA_RISC_V_NPU_Simulator)](https://www.notion.so/wiki/che-yjwj/IA_RISC_V_NPU_Simulator#2.2)
- [Event-Driven Migration (che-yjwj/IA_RISC_V_NPU_Simulator)](https://www.notion.so/wiki/che-yjwj/IA_RISC_V_NPU_Simulator#2.5)

### Citations

**File:** ia_risc_v_npu/src/simulator/events.py (L13-22)

```python
@dataclass(order=True)
class _ScheduledEvent:
    sort_index: Tuple[int, int] = field(init=False, repr=False)
    timestamp: int
    order: int
    callback: EventCallback = field(compare=False)

    def __post_init__(self) -> None:
        self.sort_index = (self.timestamp, self.order)

```

**File:** ia_risc_v_npu/docs/prd.md (L276-278)

```markdown
- Week 4: 5-8 MIPS
- Week 8: 8-12 MIPS
- Week 12: 12-20 MIPS

```

**File:** ia_risc_v_npu/specs/tasks-event-only-migration.md (L10-12)

```markdown
- [x] 결정성 환경 고정 스크립트 추가(OPENBLAS/MKL 스레드 1, NumPy RNG 시드)
  - 수용기준: 동일 입력 N회 실행 시 결과 해시/타임라인 동일
  - 완료: `scripts/deterministic_env.py` 도입, 통합 테스트 2회 반복 시 `sha256=0e26f8d6…` 동일 출력 확인

```

**File:** ia_risc_v_npu/specs/tasks-event-only-migration.md (L33-101)

```markdown
## Phase 2 – Bus 이벤트화 (주 2–3)

- [ ] `src/simulator/memory.py:Bus` rr 중재/슬라이스/대역폭/그랜트 지연 구현
  - 수용기준: 요청 bytes, slice_bytes, bandwidth로 예측 가능한 done_at 도출
- [ ] Bus 요청/완료 통계 수집(옵저버) 추가
  - 수용기준: 평균 대기/전송 시간, 큐 길이 리포트 가능

---

## Phase 3 – DRAM 은행/로우버퍼 (주 3–4)

- [ ] `MemorySystem.DRAM` 상태(bank_free_at,row_open) 및 지연 모델(tRP,tRCD,tCAS)
  - 수용기준: row-hit/miss 케이스가 서로 다른 done_at 반환
- [ ] 주소 매핑 함수(bank,row) 구성화 및 테스트
  - 수용기준: bank 라운드로빈 분산 확인(합성 주소군)

---

## Phase 4 – 캐시 계층 (주 4–5)

- [ ] L1/L2 태그/인덱스/연관도/교체정책(FIFO 또는 pseudo LRU)
  - 수용기준: 히트/미스 판정과 라인 채움 이벤트 연결
- [ ] `MemorySystem.load/store` 상위 API 제공
  - 수용기준: 동일 주소 접근 시 캐시 히트 지연 적용

---

## Phase 5 – CPU 마이크로타이밍 (주 5–6)

- [ ] 분기 예측/패널티(정적 backwards taken, mispredict_penalty)
  - 수용기준: 분기 패턴별 사이클 차이 재현
- [ ] 로드‑유즈 스톨(메모리 done_at과 의존 간격 기반)
  - 수용기준: load→use 시 스톨 1cy 이상 삽입 검증
- [ ] MUL/DIV 지연(구성값 반영)
  - 수용기준: 루프에서 CPI 변화 인지
- [ ] I‑캐시 미스 프런트엔드 스톨
  - 수용기준: 미스율에 따른 페치 지연 반영

---

## Phase 6 – NPU Cluster + DMA (주 6–8)

- [ ] `src/npu/cluster.py` 도입(cores, core_free_at, submit)
  - 수용기준: 단일 코어/멀티 코어 모두 동작, done_at 산출
- [ ] DMA 슬라이스 전송(Bus 사용) 및 compute 파이프라인
  - 수용기준: 입력/출력 전송+연산이 직렬/겹침 규칙대로 합산
- [ ] 정책: min_finish_time/rr 선택 가능
  - 수용기준: 동일 작업군에서 코어 선택 차이 확인

---

## Phase 7 – 구성/리포트/정확도 가드 (주 8–10)

- [ ] JSON 스키마 검증기(필수키/범위/열거형), schema_version 예약
  - 수용기준: 잘못된 구성 시 시뮬레이터 시작 실패
- [ ] 리포트 확장: miss_rates, AMAT, stall_breakdown, npu_util
  - 수용기준: CLI 출력/파일에 지표 포함
- [ ] 정확도 가드 파이프라인(골든 대비 편차 계산)
  - 수용기준: 임계 초과 시 실패 코드 반환 및 요약 출력

---

## Phase 8 – 테스트/벤치/정리 (주 10–12)

- [ ] 결정성 테스트: 동일 입력 다회 실행 동일 타임라인
- [ ] 성능 벤치: 8–12 MIPS 범위 확인(간단 ADD 워크로드 기준)
- [ ] 문서 갱신: README, PRD 링크, 기술 설계서/작업 문서 최신화
- [ ] 레거시 훅 코드 제거 및 주석 정리

```

**File:** ia_risc_v_npu/docs/technical-design-event-only.md (L61-75)

```markdown
Bus(이벤트화)
- 상태: per-master 대기열, 현재 슬라이스 진행중 전송, last_grant_idx.
- 파라미터: rr|weighted, slice_bytes, grant_latency, bandwidth_bytes_per_cycle.
- API: request(master_id: int, bytes: int) -> (grant_at: int, done_at: int)
  1) 요청 도착(now) 시 대기열 등록
  2) 중재 이벤트에서 grant_latency 후 전송 시작
  3) bytes를 slice_bytes로 분할, 각 슬라이스에 전송 지연 = ceil(slice_bytes / bw)
  4) 모든 슬라이스 완료 시 done_at 산출 및 콜백/리턴

DRAM(은행/로우버퍼)
- 상태: bank_free_at[banks], row_open[banks] (open row id or None)
- 주소 매핑: bank = (addr/line) % banks, row = (addr // row_size)
- 지연: row-hit=tCAS, row-miss=tRP+tRCD+tCAS
- API: access(addr: int, size: int) -> done_at(int)
  - bank 시각을 고려해 활성/프리차지/컬럼 접근 이벤트 체인 생성

```

**File:** ia_risc_v_npu/docs/technical-design-event-only.md (L106-116)

```markdown
구성 요소
- NPUCore: core_free_at 시각 보유, compute(op) 지연은 op 특징(작업량/구성)으로 산정.
- DMA 엔진: dma_slice_bytes 단위로 메모리 전송 이벤트 발행(Bus 사용).
- 스케줄 정책: min(core_free_at) 기본, min_finish_time/rr/weighted 지원.

API
- submit(op) -> done_at: 입력/출력 DMA 전송과 compute를 파이프라이닝. 최종 done_at 반환.

정확도 힌트
- GEMM/Conv와 같은 연산은 MAC 카운트 기반으로 compute 지연 근사
  (참고: ia_risc_v_npu/src/simulator/cnn_utils.py:estimate_mac_count 사용 가능).

```

**File:** ia_risc_v_npu/docs/prd_v2.md (L17-17)

```markdown
- 성능(보조): 기본 8–12 MIPS, 최적화 시 12–15 MIPS. 정확도 가드 준수가 우선.

```
