# Stage 9 — Documentation & Visualization Roadmap

## 1. Goal
- Stage 8에서 완성한 CQ 실행/accuracy 경로를 사용자 문서와 시각화 자산으로 정리한다.
- CQ-BG-008 범위를 세부 작업으로 분할하고, 자동화/튜토리얼 항목을 명확히 정의한다.

## 2. Deliverables
| Workstream | Deliverable | Files/Tools |
|------------|-------------|-------------|
| Reference | ISA/CQ 명세 자동 추출 → Markdown/HTML 요약 | `scripts/generate_cq_models.py` 출력 + `docs/reference/` |
| Visualization | CQ Timeline/Gantt CSV 생성 스크립트 + 예시 그래프 | 새 스크립트 `src/scripts/cq_timeline_export.py`, Plotly/Matplotlib 노트북 |
| Tutorial | CQ 실행/Accuracy Guard 워크플로 포함 노트북 | `notebooks/cq_pipeline_walkthrough.ipynb` |
| CLI Docs | `run-cq --simulate`/lane usage/Accuracy Guard 활용 가이드 | `docs/tutorials/cq_pipeline.md`, `docs/reference/cli.md` |

## 3. Task Breakdown
1. **Reference Automation**
   - `specs/`와 `src/cq/generated/*`를 활용해 ISA opcode/operand 표 생성.
   - CQ schema 요약(필드/타입/트레이스 필드).
   - 결과를 `docs/reference/isa_cq_reference.md`로 출력하는 스크립트 작성.
2. **Timeline Export**
   - `AdaptiveSimulator.run_cq_trace` 결과에서 이벤트 타임스탬프 수집 (`dispatch.timestamps`).
   - CSV 포맷: `cmd_id,start_tick,end_tick,lane`.
   - 샘플 notebook에서 Gantt 시각화 (Plotly Express).
3. **Tutorial Notebook**
   - `run-cq --simulate` 실행 → Accuracy Guard 비교 → Lane usage 해석.
   - CLI ↔ Python API ↔ Golden 통합 시나리오 포함.
4. **Documentation Update**
   - 튜토리얼/README에 새 스크립트와 노트북 링크 추가.
   - Stage 8 설계 문서 링크 정리 (`cq_run_cli_extension.md`, `cq_lane_metrics_golden_integration.md`).

## 4. Timeline & Milestones
- Week 1: Reference generator 스크립트 + CLI 문서 초안.
- Week 2: Timeline export 도구 + 플롯 노트북 초안.
- Week 3: Tutorial notebook 정리 + Accuracy Guard 연계 검증.
- Week 4: QA/리뷰, Stage 9 체크리스트 마감.

## 5. Dependencies
- Stage 8 문서 (`cq_run_cli_extension.md`, `cq_lane_metrics_golden_integration.md`).
- Golden workload summaries (lane usage 포함).
- Plotting 라이브러리(Plotly/Matplotlib) 선택 시 requirements 업데이트 필요 여부 확인.

## 6. Risks & Mitigations
- 시각화 라이브러리 도입 → 의존성 증가 가능 → 선택적 설치 안내, CI optional path.
- 자동 생성 문서가 spec 변경에 민감 → 스크립트 CI hook에 포함, 실패 시 알람.
- Tutorial 실행 시간이 길어질 경우 → 샘플 워크로드 축소, 캐시된 출력 제공.

## 7. Progress Notes (Stage 9)
- `python -m src.scripts.generate_isa_cq_reference`가 `specs/isa.yaml`과
  `src/cq/cq.schema.json`에서 문서를 생성하도록 구현 완료.
- `python -m src.scripts.cq_timeline_export`는 `dispatch.timeline`을 CSV로 변환해
  Plotly/Matplotlib 입력으로 활용 가능.
- `docs/tutorials/cq_pipeline.md` 및 `notebooks/cq_pipeline_walkthrough.ipynb`에
  `run-cq --simulate` 워크플로와 Accuracy Guard/TML 시각화 경로를 정리.
