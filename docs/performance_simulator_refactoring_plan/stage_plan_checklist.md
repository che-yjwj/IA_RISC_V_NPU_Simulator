Stage 0 — 리포 준비 & 가드레일
- [x] feature 브랜치 생성
- [x] CQ 전용 디렉토리 추가
- [x] CLI `run-cq` 엔트리 추가
- [x] 기존 ELF 경로 회귀 테스트 보존 (백로그 `CQ-BG-001`, `tests/integration/test_cli_run_simulate.py`)

## Stage 1 — 최소 스펙 정의
- [x] `isa.yaml`: TE_GEMM, DMA_2D, FENCE_SPM
- [x] `cq.schema.json`: cmd_id, opcode, operands, deps, trace
- [x] 샘플 CQ.jsonl 파일 생성
- [x] Lint & Schema 검증 통과

## Stage 2 — CQ I/O + 실행 골격
- [x] `cq/io.py`: JSONL reader/writer
- [x] CLI `run-cq path/to/trace.jsonl`
- [ ] trace_id 체계 (ir_id → isa_idx → cmd_id) (백로그 `CQ-BG-005`)

## Stage 3 — Dispatcher CQ Consumer
- [x] `src/cq/dispatcher.py` 구현 (스켈레톤, 상태 추적 포함)
- [x] CQ 엔트리 상태 전이 (queued→scheduled→done)
- [x] trace_id 로깅
- [x] 요약 통계 (num_cmds, avg_queue_wait)
- [x] 통합 테스트 `tests/integration/test_cq_dispatcher.py`로 기본 흐름 검증
- [x] `AdaptiveSimulator.run_cq_trace` 액션 로거 스텁
- [x] CQ DMA/GEMM 실행이 버스/NPU 클러스터 타이밍과 연동

## Stage 4 — 자원/타이밍/경합 모델
- [ ] spm.py: bank/port 충돌 (백로그 `CQ-BG-003`)
- [ ] bus.py: slice 단위 모델 (백로그 `CQ-BG-003`)
- [ ] dma.py: row-based 지연 (백로그 `CQ-BG-003`)
- [ ] te.py: GEMM 지연 근사 (백로그 `CQ-BG-003`)
- [ ] Deadlock 감지 로직 (백로그 `CQ-BG-003`)
- [x] CQ vs ELF 비교 스텁 (`src/simulator/cq_runner.py`) 마련
- [x] CQ 텐서 초기화/실데이터 주입 (`AdaptiveSimulator.load_cq_tensors`)

## Stage 5 — Spec-Codegen v1
- [ ] `isa.yaml` → dataclass 자동 생성 (백로그 `CQ-BG-002`)
- [ ] `cq.schema.json` → Pydantic 모델 생성 (백로그 `CQ-BG-002`)
- [ ] pre-commit 훅 추가 (백로그 `CQ-BG-002`)

## Stage 6 — IR→ISA & ISA→CQ 변환
- [ ] `rules/*.yaml`: Conv/Copy 룰 정의 (백로그 `CQ-BG-005`)
- [ ] mapper.py: 룰 엔진 구현 (백로그 `CQ-BG-005`)
- [ ] cq/generator.py: ISA → CQ 변환 (백로그 `CQ-BG-005`)

## Stage 7 — Accuracy Guard & Golden Test
- [ ] 골든 워크로드 5종 준비 (백로그 `CQ-BG-006`)
- [ ] golden diff CI 통합 (백로그 `CQ-BG-006`)
- [ ] 허용 편차 정책 설정 (백로그 `CQ-BG-006`)

## Stage 8 — 모델 정밀도/정책 확장
- [ ] 스케줄 정책 (RR, EDF) (백로그 `CQ-BG-007`)
- [ ] 멀티-TE, 멀티-DMA lane (백로그 `CQ-BG-007`)

## Stage 9 — 문서화/시각화
- [ ] ISA/CQ Reference 자동 생성 (백로그 `CQ-BG-008`)
- [ ] Gantt chart/Timeline CSV 산출 (백로그 `CQ-BG-008`)
- [ ] 튜토리얼 노트북 작성 (백로그 `CQ-BG-008`)
