# 이벤트 전용(무훅) 마이그레이션 작업 목록 (MVP 12주)

목표: PRD v2.1 및 기술 설계서에 따른 이벤트 전용 하이브리드 시뮬레이터를
정확도 우선 기준으로 구현/검증한다. 아래 작업은 단계별 선행관계를 반영한다.

---

## Phase 0 – 준비 (주 0–1)

- [x] 결정성 환경 고정 스크립트 추가(OPENBLAS/MKL 스레드 1, NumPy RNG 시드)
  - 수용기준: 동일 입력 N회 실행 시 결과 해시/타임라인 동일
  - 완료: `scripts/deterministic_env.py` 도입, 통합 테스트 2회 반복 시 `sha256=0e26f8d6…` 동일 출력 확인
- [x] CI에서 `pytest -q`, `pytest tests/performance --benchmark-only` 잡 구성
  - 수용기준: 실패 시 아티팩트로 리포트 JSON 업로드
  - 완료: `.github/workflows/ci.yml` 작성, 실패 시 JSON 리포트 업로드 및 Deterministic helper로 실행

---

## Phase 1 – EventScheduler 도입 (주 1–2)

- [x] `src/simulator/events.py` 힙 기반 스케줄러 구현(now/schedule/run)
  - 수용기준: 단위 테스트에서 동시간 이벤트 id 순서 보장
  - 완료: `EventScheduler` 도입 및 `tests/unit/test_events.py` 커버리지 확보(PR 준비 브랜치 `feature/event-scheduler-migration`)
- [x] `src/simulator/main.py:AdaptiveSimulator`를 이벤트 구동으로 전환
  - 수용기준: 기존 통합 테스트 유지, 훅 비의존 경로로 동작
  - 완료: `AdaptiveSimulator.run_simulation`이 스케줄러 기반 루프로 교체, fetch 훅 지연을 이벤트로 연결
- [x] `src/simulator/hooks.py` 제거 또는 옵저버로 축소(결정성 위반 요소 제거)
  - 수용기준: time.time()/난수 사용 제거
  - 완료: 난수 선표와 타임스탬프 제거, 결정적 계측 버퍼만 유지

---

## Phase 2 – Bus 이벤트화 (주 2–3)

- [x] `src/simulator/memory.py:Bus` rr 중재/슬라이스/대역폭/그랜트 지연 구현
  - 수용기준: 요청 bytes, slice_bytes, bandwidth로 예측 가능한 done_at 도출
  - 완료: 슬라이스 기반 라운드로빈 버스 모델을 도입하고 `RISCVEngine`/`AdaptiveSimulator`에서 done_at을 활용하도록 통합.
- [x] Bus 요청/완료 통계 수집(옵저버) 추가
  - 수용기준: 평균 대기/전송 시간, 큐 길이 리포트 가능
  - 완료: `BusMetrics.snapshot()`을 리포트/CLI 요약에 포함하며 단위/검증 테스트로 통계 집계를 검증.

---

## Phase 3 – DRAM 은행/로우버퍼 (주 3–4)

- [x] `MemorySystem.DRAM` 상태(bank_free_at,row_open) 및 지연 모델(tRP,tRCD,tCAS)
  - 수용기준: row-hit/miss 케이스가 서로 다른 done_at 반환
  - 완료: `DRAMConfig/DRAM` 클래스 추가하여 은행/로우 상태 추적 및 지연 반영
- [x] 주소 매핑 함수(bank,row) 구성화 및 테스트
  - 수용기준: bank 라운드로빈 분산 확인(합성 주소군)
  - 완료: `tests/unit/test_simulator_memory.py`에 bank 라운드로빈/row-hit 검증 추가

---

## Phase 4 – 캐시 계층 (주 4–5)

- [x] L1/L2 태그/인덱스/연관도/교체정책(FIFO 또는 pseudo LRU)
  - 수용기준: 히트/미스 판정과 라인 채움 이벤트 연결
- [x] `MemorySystem.load/store` 상위 API 제공
  - 수용기준: 동일 주소 접근 시 캐시 히트 지연 적용

---

## Phase 5 – CPU 마이크로타이밍 (주 5–6)

- [x] 분기 예측/패널티(정적 backwards taken, mispredict_penalty)
  - 수용기준: 분기 패턴별 사이클 차이 재현
- [x] 로드‑유즈 스톨(메모리 done_at과 의존 간격 기반)
  - 수용기준: load→use 시 스톨 1cy 이상 삽입 검증
- [x] MUL/DIV 지연(구성값 반영)
  - 수용기준: 루프에서 CPI 변화 인지
- [x] I‑캐시 미스 프런트엔드 스톨
  - 수용기준: 미스율에 따른 페치 지연 반영

---

## Phase 6 – NPU Cluster + DMA (주 6–8)

- [x] `src/npu/cluster.py` 도입(cores, core_free_at, submit)
  - 수용기준: 단일 코어/멀티 코어 모두 동작, done_at 산출
- [x] DMA 슬라이스 전송(Bus 사용) 및 compute 파이프라인
  - 수용기준: 입력/출력 전송+연산이 직렬/겹침 규칙대로 합산
- [x] 정책: min_finish_time/rr 선택 가능
  - 수용기준: 동일 작업군에서 코어 선택 차이 확인

---

## Phase 7 – 구성/리포트/정확도 가드 (주 8–10)

- [x] JSON 스키마 검증기(필수키/범위/열거형), schema_version 예약
  - 수용기준: 잘못된 구성 시 시뮬레이터 시작 실패
  - 완료: `src/simulator/config.py`에서 기본값/검증 로직 제공, CLI 로딩 시 `ConfigValidationError`로 실패 처리
- [x] 리포트 확장: miss_rates, AMAT, stall_breakdown, npu_util
  - 수용기준: CLI 출력/파일에 지표 포함
  - 완료: `SimulationReport`에 캐시/메모리/NPU/페치 메트릭 추가, `prepare_summary`가 miss_rates·AMAT·stall_breakdown·npu_util 계산/노출
- [x] 정확도 가드 파이프라인(골든 대비 편차 계산)
  - 수용기준: 임계 초과 시 실패 코드 반환 및 요약 출력
  - 완료: `src/simulator/accuracy.py` 도입, CLI에서 골든 요약 비교 후 실패 시 종료코드 1 반환 및 `accuracy_guard` 섹션 기록. 데모 워크로드(`workloads/demos/accuracy_guard/`)로 사용법 예시 제공

---

## Phase 8 – 테스트/벤치/정리 (주 10–12)

- [ ] 결정성 테스트: 동일 입력 다회 실행 동일 타임라인
- [ ] 성능 벤치: 8–12 MIPS 범위 확인(간단 ADD 워크로드 기준)
- [ ] 문서 갱신: README, PRD 링크, 기술 설계서/작업 문서 최신화
- [ ] 레거시 훅 코드 제거 및 주석 정리

---

## 테스트/검증 포인트(파일/명령)

- 단위: `pytest tests/unit -vv`
- 통합: `pytest tests/integration -vv`
- 성능: `pytest tests/performance --benchmark-only`
- 전체: `pytest`
- 시뮬레이터: `python -m src.simulator.cli simulate <elf> --config <json>`
- 벤치: `python -m src.simulator.cli benchmark --instructions 200000`

---

## 코드 연결 고리(참고)

- 스케줄러 진입점: ia_risc_v_npu/src/simulator/main.py:40
- 훅 제거 대상: ia_risc_v_npu/src/simulator/hooks.py:4
- 버스/메모리: ia_risc_v_npu/src/simulator/memory.py:1
- CPU IA: ia_risc_v_npu/src/risc_v/engine.py:1
- NPU 모델(현행 단일): ia_risc_v_npu/src/npu/model.py:1
- CLI: ia_risc_v_npu/src/simulator/cli.py:1

---

## 완료 정의(DoD)

- 결정성: 동일 구성/입력에 대해 타임라인/리포트 해시가 안정적
- 정확도: 벤치셋 평균/중앙값 ±15% 이내, 단일 케이스 ±20% 미만
- 성능: 기본 8–12 MIPS 달성(정확도 모드)
- 문서: 설계/작업/구성 스키마 설명 및 사용법 정리
