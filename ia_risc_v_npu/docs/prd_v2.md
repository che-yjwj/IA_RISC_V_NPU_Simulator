# 정확도 우선 이벤트 전용(무훅) 시뮬레이터 PRD v2.1

**제목**: 무훅(Event-Only) 하이브리드 RISC-V+NPU 시뮬레이터 PRD (정확도 우선)

**작성일**: 2025-09-21

**목표 기간**: 12주 (MVP)

**버전**: 2.1

---

## 1. 개요

- 목표: 시스템 정확도(±15%)를 최우선으로, 모든 시간 진행을 단일 이벤트 스케줄러(모의 시간)로 통합하고 훅(타이밍 훅)을 제거한 결정적(discrete-event) 하이브리드 시뮬레이터를 구축한다.
- 범위: CPU는 IA(Instruction-Accurate) + 경량 타이밍 마이크로모델, 메모리/버스/비동기 NPU는 로컬 이벤트(소형 DES) 기반. 훅은 제거하고, 관찰용 옵저버만 선택적으로 허용.
- 성능(보조): 기본 8–12 MIPS, 최적화 시 12–15 MIPS. 정확도 가드 준수가 우선.

이 문서는 `docs/prd_accuracy_no_hooks.md`를 재검토하고, 구성 스키마/검증 기준/결정성 정책/멀티코어 NPU 스케줄링/마이그레이션 체크리스트를 보강한다.

---

## 2. 현 코드베이스 기준 (2025-09)

- RISC-V 엔진: `ia_risc_v_npu/src/risc_v/engine.py` – IA 위주. 분기 패널티/로드‑유즈/I‑캐시 타이밍은 미약 → 경량 타이밍 보강 필요.
- NPU: `ia_risc_v_npu/src/npu/model.py` – 벡터 연산 4종(v_add/sub/mul/div). GEMM/DMA/비동기/멀티코어 미구현 → NPUCluster가 필요.
- 메모리/버스: `src.simulator.memory:Bus`를 테스트에서 사용(`ia_risc_v_npu/tests/performance/test_performance.py:5`). 큐잉/중재/전송의 이벤트화 및 DRAM 은행/로우버퍼 모델 추가 필요.
- 테스트 자산: `ia_risc_v_npu/tests/{unit, integration, performance, verification}`. 정확도 회귀와 결정성 테스트 보강 필요.

---

## 3. 범위/제약

### 3.1 범위

- ISA: RV32I + 선택적 M(MUL/DIV) (MVP). Phase 2에서 RV64I 확장.
- 이벤트 리소스: Bus(중재/전송), DRAM(은행/로우버퍼), NPU Cluster(코어 N, DMA 포함).
- CPU 타이밍: 분기 패널티(간단 예측기), 로드‑유즈 스톨, MUL/DIV 지연, I‑캐시 미스 스톨을 이벤트와 동기화.
- 인터페이스: CLI 실행, JSON 리포트, 정확도 가드(이벤트 전용이 기본).

### 3.2 제약

- Python 3.10+, 메모리 ≤ 8 GB.
- asyncio/실시간 타이머 금지(시간은 이벤트 스케줄러만 결정).
- 결정성 필수: 동일 입력→동일 타임라인/통계.
- 장시간(≥1h) 안정 실행.

---

## 4. 구성 스키마(초안)

```json
{
  "accuracy_guard": {"target_pct": 15, "max_case_pct": 20},
  "cpu": {
    "mul_div_cycles": {"mul": 3, "div": 12},
    "branch": {"predictor": "static_backwards_taken", "mispredict_penalty": 3},
    "load_use_stall": 1,
    "icache": {"lat": 1, "miss_penalty": 20}
  },
  "cache": {
    "l1": {"lat": 1, "size": 32768, "assoc": 4},
    "l2": {"lat": 12, "size": 262144, "assoc": 8}
  },
  "dram": {
    "banks": 8,
    "tCAS": 12,
    "tRCD": 12,
    "tRP": 12
  },
  "bus": {
    "arb": "rr",          
    "slice_bytes": 64,
    "grant_latency": 2,
    "bandwidth_bytes_per_cycle": 32
  },
  "npu": {
    "cores": 1,
    "policy": "min_finish_time",
    "dma_slice_bytes": 256
  },
  "determinism": {
    "seed": 1234,
    "blas_threads": 1,
    "tie_breaker": "monotonic_id"
  }
}
```

- 유효성: 누락/범위 오류는 시뮬레이터 시작 시 실패 처리. 스키마 버전 필드(`schema_version`)는 향후 추가.

---

## 5. 기능 요구사항

1) 이벤트 커널(EventScheduler)
- 우선순위 힙 기반; `now`, `schedule(at, fn, *args)`, `run()`, `run_until(t)`.
- 동일 타임스탬프 이벤트는 증가 ID로 안정 정렬(결정성).

2) 버스(Bus) 이벤트화
- API: `request(master_id, bytes) -> (grant_at, done_at)`.
- 정책: 라운드로빈/가중치; 버스트/슬라이스; 대역폭/지연 파라미터화.
- 관찰성: 큐 길이/대기시간 측정(옵저버), 통계 이벤트만 노출.

3) DRAM 이벤트화
- API: `access(addr, size) -> done_at`.
- 은행/로우버퍼 상태(`bank_free_at[]`, `row_open[]`), row‑hit/row‑conflict 차등 지연(tRP/tRCD/tCAS).

4) 캐시 계층
- L1/L2 히트는 상수 지연(+1/+L2lat). 미스 시 버스/DRAM 이벤트 트리거, 라인 채움 완료를 이벤트로 모델.

5) NPU Cluster(멀티코어 확장)
- API: `submit(op) -> done_at`.
- 코어 선택: `min(core_free_at)` 기본; 정책 전환 가능(rr, weighted, min_finish).
- DMA/버스 이벤트를 타일 단위로 생성; CPU‑NPU 동기 지점에서 정확 대기.

6) CPU 타이밍 마이크로모델
- ALU=1cy, MUL/DIV=구성값. 분기 패널티=간단 예측기+미스율 기반.
- 로드‑유즈: 메모리 완료 이벤트의 `done_at`과 의존 간격으로 스톨 삽입.
- I‑캐시 미스: 프런트엔드 스톨을 버스/DRAM 이벤트 완료와 동기화.

7) 리포트/구성
- 출력: `cycles, mips, cpi, miss_rates, AMAT, stall_breakdown{dram,bus,npu_wait}, npu_util, top_bottlenecks`.
- 정확도 가드: 골든 대비 평균/중앙값 ±15%, 단일 케이스 ±20% 초과 시 실패.

---

## 6. 결정성/재현성 정책

- 동일 입력은 동일 타임라인/통계 산출.
- 타이브레이커: 이벤트 엔큐 시 증가 ID를 부여, `(time, id)`로 정렬.
- 수치 결정성: BLAS/NumPy 스레드 수 고정(예: `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`).
- RNG/샘플링: 모든 무작위 경로는 `determinism.seed`로 초기화.

---

## 7. 정확도 정의/벤치셋

- 지표: 총 사이클/총 시간, MIPS, DRAM/Bus/NPU 대기 비중, miss rates, AMAT.
- 벤치셋(초기): rv32ui/um, stride/random, branch‑heavy, mul/div loop, SAXPY, 소타일 GEMM, conv‑like, CPU‑NPU 혼합.
- 판정: `abs(model−golden)/golden×100[%]`의 평균/중앙값 ≤15%, 단일 케이스 20% 초과 없음.
- 골든 소스: 우선 내부 준사이클 모델/레퍼런스 로그. 외부 레퍼런스 도입 시 문서화.

---

## 8. 아키텍처(무훅)

```
┌───────────────────────────────────────────────┐
│                 Event-Only Kernel            │
├───────────────┬──────────────┬──────────────┤
│     CPU IA    │   Memory     │     NPU      │
│ + micro-time  │ (L1/L2/DRAM) │   Cluster    │
│  (no hooks)   │   events     │    events    │
├───────────────┴──────────────┴──────────────┤
│              Global Time = events            │
└───────────────────────────────────────────────┘
```

핵심: 모든 지연/겹침/경합은 이벤트로 스케줄. 훅은 제거(옵저버만 선택적).

---

## 9. API 요약

- `EventScheduler`: `now`, `schedule(at, fn, *args)`, `run()`, `run_until(t)`.
- `Bus.request(master_id, bytes) -> (grant_at, done_at)`.
- `DRAM.access(addr, size) -> done_at`.
- `MemorySystem.load/store(addr, size) -> done_at` (캐시 히트/미스 포함).
- `NPUCluster.submit(op) -> done_at`.
- `CPU.exec(inst)`: 필요 시 메모리/NPU 호출, 반환된 `done_at`과 동기화해 스톨 계산.

---

## 10. 마이그레이션 체크리스트(훅 제거)

- [ ] `src/simulator/events.py` 추가(힙 기반 결정적 스케줄러)
- [ ] `src/simulator/memory.py` 버스/DRAM 이벤트화(은행/로우버퍼 포함)
- [ ] `src/npu/cluster.py` 도입(코어 N, DMA/버스 이벤트 생성)
- [ ] `src/risc_v/engine.py` 타이밍 보강(분기/로드‑유즈/MUL‑DIV/I‑미스)
- [ ] CLI 동기 실행으로 정리(`src/simulator/cli`)
- [ ] 훅 코드/정책/테스트 제거 또는 옵저버로 축소
- [ ] 결정성 테스트 추가(동일 입력→동일 타임라인)
- [ ] 정확도 가드 회귀 파이프라인 추가

---

## 11. 빌드/테스트 지침

- 설치: `pip install -r ia_risc_v_npu/requirements.txt`
- 단위 테스트: `pytest tests/unit -vv`
- 전체: `pytest`
- 성능 벤치: `pytest tests/performance --benchmark-only`
- 시뮬레이터 실행: `python -m src.simulator.cli simulate <elf> --config <json>`
- 벤치마크: `python -m src.simulator.cli benchmark --instructions 200000`

---

## 12. 위험/대응

- 성능 저하: 이벤트 범위 제한(메모리/버스/NPU), 배치/슬라이스/샘플링.
- 복잡도 증가: API 최소화, 컴포넌트 인터페이스 표준화.
- 파라미터 민감: 캘리브레이션 루프(골든/트레이스 기반), 변경 이력 관리.
- BLAS/NumPy 비결정성: 정확도 모드에서 단일 스레드 고정, CI에서 확인.

---

## 13. 성공 기준

- 정확도: 평균/중앙값 ±15% 이내, 단일 케이스 ±20% 초과 없음.
- 성능: 이벤트 전용 모델 기준 8–12 MIPS 이상, 최적화로 12–15 MIPS 근접.
- 결정성/안정성: 동일 입력 동일 타임라인, 1시간 연속 실행 통과.
- 리포트 신뢰: stall_breakdown/AMAT/miss_rates가 골든 추세와 일치.

---

## 14. 부록 – 변경 요약(무훅)

- 시간 진행: 훅 합산 → 이벤트 스케줄러 단일 원천.
- 지연 계산: 훅 테이블 → 리소스 내부 상태(Bus/DRAM/NPU) 기반.
- 관찰성: 훅 로깅 → 이벤트 옵저버(선택).
- 정책: 이벤트 전용으로 고정 운영(정확도 가드 기본 활성화, 빠른 근사 모드는 제공하지 않음).
