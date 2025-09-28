<!-- encoding: UTF-8 -->
# 정확도 우선 이벤트 전용 시뮬레이터 기술 설계서 (v1)

문서 목적: PRD v2.1의 이벤트 전용(무훅) 하이브리드 RISC-V+NPU 시뮬레이터를
12주 MVP 범위로 구현하기 위한 기술 아키텍처, 컴포넌트 설계, API, 결정성 정책,
테스트/측정 전략을 정의한다.

참고 문서: ia_risc_v_npu/docs/prd_v2.md

---

## 1. 전체 목표와 범위

- 정확도 우선: 평균/중앙값 오차 ±15% 이내(단일 케이스 ±20%).
- 시간의 단일 근원: 이벤트 스케줄러(DES)만이 모의 시간을 결정.
- 훅 제거: 기존 훅 기반 지연은 폐기, 관찰용 옵저버만 선택적 허용.
- 범위: CPU IA + 경량 타이밍, Bus/DRAM 이벤트화, L1/L2 캐시, NPU Cluster(DMA 포함).
- 성능 보조 목표: 8–12 MIPS(정확도 모드). 최적화 시 12–15 MIPS 근접.

---

## 2. 아키텍처 개요

글로벌 시간 = 이벤트. 각 리소스는 자체 상태와 이벤트를 통해 경합/겹침/대기 표현.

컴포넌트
- EventScheduler: 전역 시간 및 이벤트 큐 관리(우선순위 힙, 타임브레이커).
- MemorySystem: L1/L2 캐시, Bus(대역폭/슬라이스/중재), DRAM(은행/로우버퍼).
- CPU(IA + 마이크로타이밍): 분기 패널티, 로드‑유즈 스톨, MUL/DIV 지연, I‑캐시 미스.
- NPU Cluster: 코어 N, DMA 슬라이스 단위 전송, 스케줄 정책.
- CLI/Config/Report: 구성 검증, 결정성 가드, 결과 리포트.

---

## 3. EventScheduler 설계

데이터 구조
- min-heap of (time: int, id: int, fn: Callable, args: tuple)
- now: int(사이클), id는 0부터 단조 증가

API
- now() -> int: 현재 모의 시간(사이클)
- schedule_at(t: int, fn, *args) -> int: t 시각에 이벤트 등록, 이벤트 id 반환
- schedule_after(delta: int, fn, *args) -> int: now+delta에 등록
- run() -> None: 큐가 빌 때까지 실행
- run_until(t: int) -> None: t 도달까지 실행

결정성
- 동일 입력 → 동일 타임라인. 동시간 이벤트는 id 오름차순으로 처리.
- 스케줄러는 RNG 비사용. 외부 난수 경로는 구성의 seed로 고정.

옵저버(선택)
- on_event_scheduled/on_event_executed 훅으로 통계 수집 전용.

---

## 4. 메모리/버스/DRAM/캐시 설계

주소 공간
- DRAM/SPM/MMIO는 기존 맵 유지(참조: ia_risc_v_npu/src/simulator/main.py:15).

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

캐시(L1/L2)
- 태그/인덱스/연관도: 구성값 사용. LRU 근사(2-bit pseudo LRU) 또는 FIFO.
- 히트: 상수 지연(lat) 후 완료.
- 미스: 버스/DRAM에 라인 채움(read-for-ownership 포함) 이벤트 발행, fill 완료 시점 반환.
- API: load/store(addr,size) -> done_at(int)

MemorySystem API(상위)
- load(addr,size)->done_at, store(addr,size)->done_at
- 내부적으로 캐시→버스→DRAM 경로를 이벤트로 연결.

---

## 5. CPU 마이크로 타이밍

기본 규칙
- ALU=1cy, MUL/DIV=구성, 메모리·I캐시 미스는 메모리 시스템 done_at과 동기화.
- 분기: 정적 예측기(backwards taken). 미스 시 mispredict_penalty 적용.
- 로드‑유즈: 선행 load의 done_at이 소비 시점보다 늦으면 스톨 삽입.

모델링 방법
- fetch: I‑캐시 lookup. 히트 시 +icache.lat, 미스 시 라인 채움 done_at까지 스톨.
- execute: 연산별 latency 누적. load/store는 MemorySystem의 done_at과 동기화.
- 이벤트 통합: CPU는 다음 유효 사이클 = max(now+local_latency, 외부 done_at)로
  self.next_ready_at를 갱신하고, EventScheduler에 ‘다음 인스트럭션 실행’ 이벤트를 등록.

---

## 6. NPU Cluster 설계

구성 요소
- NPUCore: core_free_at 시각 보유, compute(op) 지연은 op 특징(작업량/구성)으로 산정.
- DMA 엔진: dma_slice_bytes 단위로 메모리 전송 이벤트 발행(Bus 사용).
- 스케줄 정책: min(core_free_at) 기본, min_finish_time/rr/weighted 지원.

API
- submit(op) -> done_at: 입력/출력 DMA 전송과 compute를 파이프라이닝. 최종 done_at 반환.

정확도 힌트
- GEMM/Conv와 같은 연산은 MAC 카운트 기반으로 compute 지연 근사
  (참고: ia_risc_v_npu/src/simulator/cnn_utils.py:estimate_mac_count 사용 가능).

---

## 7. 구성(JSON)과 CLI

구성 스키마(요지)
- cpu.mul_div_cycles, cpu.branch(predictor, mispredict_penalty), cpu.load_use_stall
- icache/ cache.l1/l2(lat,size,assoc)
- dram(banks,tCAS,tRCD,tRP), bus(arb,slice_bytes,grant_latency,bandwidth)
- npu(cores,policy,dma_slice_bytes), determinism(seed,blas_threads,tie_breaker)

검증
- 필수 키 타입/범위 확인, 누락 시 실패. schema_version 예약.
- 구현: `src/simulator/config.validate_simulator_config`가 JSON을 정규화하고 잘못된 값은 `ConfigValidationError`로 거부.

CLI 연계
- simulate/benchmark 명령의 --config를 위 스키마로 검증 후 주입.
- 결정성 모드: OPENBLAS_NUM_THREADS/MKL_NUM_THREADS=1 강제, numpy RNG 시드 설정.

리포트
- cycles, instructions, sim_time, elapsed_seconds, mips
- bus_metrics(대기/전송 집계), cache_metrics(히트/미스·miss_rate), memory_metrics(average_latency, bus_transaction_latency)
- fetch_metrics(미스율, miss_penalty), stall_breakdown{icache,bus,dram,npu_wait}, npu_metrics(utilization 포함)
- `prepare_summary`가 CLI/파일 출력에 miss_rates·AMAT·npu_util 계산을 포함

정확도 가드
- 구성: `accuracy_guard.enabled/golds_path/max_average_deviation/max_single_deviation`
- 구현: `src/simulator/accuracy.evaluate_accuracy_guard`가 골든 요약(JSON)을 평탄화하여 편차 계산, 기준 초과 시 CLI 종료코드 1 반환 후 요약에 `accuracy_guard` 섹션 기록
- 샘플: `workloads/demos/accuracy_guard/`에 구성/골든/README 제공

---

## 8. 결정성 정책

- 스케줄러 타임브레이커: (time, id). id는 등록 순서 단조 증가.
- RNG: determinism.seed로 초기화. 외부 난수 호출 금지/봉인.
- 수치 라이브러리: BLAS/NumPy 스레드 1 고정.

---

## 9. 이행 전략(요약)

1) EventScheduler 추가 및 시뮬레이터 루프 리팩터링(훅 제거)
2) Bus 이벤트화 → DRAM(은행/로우버퍼) → 캐시 계층 추가
3) CPU 마이크로타이밍(분기/로드‑유즈/MUL‑DIV/I‑미스) 반영
4) NPU Cluster + DMA + 정책 스케줄
5) 구성 스키마 검증/리포트 확장/결정성 가드
6) 테스트/벤치/성능 검증 및 튜닝

---

## 10. 테스트 전략

단위
- EventScheduler: 동시간 이벤트 순서/타임브레이커, run_until 경계
- Bus: rr 공정성, slice 전송 시간, 대역폭 적용
- DRAM: row-hit/miss 지연, 은행 독립성
- Cache: 인덱싱/태그 매칭/교체 정책, 미스 시 채움 이벤트 발생
- CPU: 분기 패널티, 로드‑유즈 스톨, MUL/DIV 지연, I‑미스 스톨
- NPU: policy별 코어 선택, DMA 분할 전송 합산 시간

통합
- CPU↔Memory 경합, CPU↔NPU 동기 지점 정확 대기
- CLI 구성/리포트 출력 검증

검증/결정성
- 동일 입력 다회 실행 → 동일 타임라인/리포트
- 정확도 가드: 골든 대비 지표 편차 계산 후 실패 처리

성능
- pytest-benchmark로 핵심 경로 측정. 8–12 MIPS 확인.

---

## 11. 리스크와 대응

- 복잡도 증가: API 최소화, 컴포넌트 인터페이스를 단순/표준화
- 성능 저하: slice/batch 단위 이벤트, 통계 옵저버만 허용
- 파라미터 민감도: 캘리브레이션 루프와 변경 이력 관리
- 외부 비결정성: 스레드/환경 고정, 테스트에 결정성 어서션 포함

---

## 12. 오픈 이슈

- DRAM 주소 매핑/row_size 구체값(워크로드 기준 캘리브레이션 필요)
- 캐시 교체 정책 단순화 수준 결정(LRU 근사 vs FIFO)
- NPU compute 모델 캘리브레이션 소스(추정식 vs 실측 로그)
- 정확도 가드의 골든 소스/승인 기준 운영 방식
