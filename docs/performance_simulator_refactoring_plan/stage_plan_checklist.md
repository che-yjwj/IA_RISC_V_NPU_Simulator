tage 0 — 리포 준비 & 가드레일
- [ ] feature 브랜치 생성
- [ ] CQ 전용 디렉토리 추가
- [ ] CLI `run-cq` 엔트리 추가
- [ ] 기존 ELF 경로 회귀 테스트 보존

## Stage 1 — 최소 스펙 정의
- [ ] `isa.yaml`: TE_GEMM, DMA_2D, FENCE_SPM
- [ ] `cq.schema.json`: cmd_id, opcode, operands, deps, trace
- [ ] 샘플 CQ.jsonl 파일 생성
- [ ] Lint & Schema 검증 통과

## Stage 2 — CQ I/O + 실행 골격
- [ ] `cq/io.py`: JSONL reader/writer
- [ ] CLI `run-cq path/to/trace.jsonl`
- [ ] trace_id 체계 (ir_id → isa_idx → cmd_id)

## Stage 3 — Dispatcher CQ Consumer
- [ ] dispatcher_cq.py 구현
- [ ] CQ 엔트리 상태 전이 (queued→scheduled→done)
- [ ] trace_id 로깅
- [ ] 요약 통계 (num_cmds, avg_queue_wait)

## Stage 4 — 자원/타이밍/경합 모델
- [ ] spm.py: bank/port 충돌
- [ ] bus.py: slice 단위 모델
- [ ] dma.py: row-based 지연
- [ ] te.py: GEMM 지연 근사
- [ ] Deadlock 감지 로직

## Stage 5 — Spec-Codegen v1
- [ ] `isa.yaml` → dataclass 자동 생성
- [ ] `cq.schema.json` → Pydantic 모델 생성
- [ ] pre-commit 훅 추가

## Stage 6 — IR→ISA & ISA→CQ 변환
- [ ] `rules/*.yaml`: Conv/Copy 룰 정의
- [ ] mapper.py: 룰 엔진 구현
- [ ] cq/generator.py: ISA → CQ 변환

## Stage 7 — Accuracy Guard & Golden Test
- [ ] 골든 워크로드 5종 준비
- [ ] golden diff CI 통합
- [ ] 허용 편차 정책 설정

## Stage 8 — 모델 정밀도/정책 확장
- [ ] 스케줄 정책 (RR, EDF)
- [ ] 멀티-TE, 멀티-DMA lane

## Stage 9 — 문서화/시각화
- [ ] ISA/CQ Reference 자동 생성
- [ ] Gantt chart/Timeline CSV 산출
- [ ] 튜토리얼 노트북 작성

