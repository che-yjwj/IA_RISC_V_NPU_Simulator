# Stage 8 Follow-up · CQ Lane Usage Golden/Accuracy Guard 통합 메모

## 1. 왜 필요한가?
- Stage 8에서 `dispatch.lane_usage`(totals, max_concurrency) 통계를 도입했지만 골든 워크로드/Accuracy Guard 리포트에는 아직 반영되지 않았다.
- CQ 실행 경로의 정확도와 자원 모델 회귀를 모니터링하려면 새로운 지표를 golden summary와 CI 리포트에 포함시켜 ±5% 편차 정책을 적용할 필요가 있다.

## 2. 현재 상태 요약
- 골든 실행은 `scripts.check_cq_accuracy`가 `workloads/golden/configs/*.json`을 읽고 `cq_accuracy_report.json`을 생성한다.
- 레인 통계는 `AdaptiveSimulator.run_cq_trace` 결과(`dispatch.lane_usage`)에서만 확인 가능하며, CLI `run-cq`는 아직 실행 경로를 노출하지 않는다.
- Accuracy Guard는 `plan_summary`, `dispatch.queue_wait`, `execution` 중심으로 비교한다; 새 키는 무시된다.

## 3. 목표
1. `scripts.check_cq_accuracy`가 `lane_usage.totals`, `lane_usage.max_concurrency`를 메트릭 목록에 추가.
2. Golden summary 파일(`workloads/golden/summaries/*.json`)에 동일한 필드가 존재하도록 재생성.
3. 허용 편차 정책을 기존 ±5% 범위와 동일하게 적용하거나 정책을 세분화(예: `max_single_deviation`는 1 덤프당 1 변화 허용)하는 방안 결정.
4. CLI (`run-cq --simulate` 예정)에서도 동일 구조를 출력하여 로컬 점검 가능.

## 4. 통합 절차 초안
1. **데이터 경로 업데이트**
   - `scripts/check_cq_accuracy.py`에서 `dispatch["lane_usage"]`를 추출해 `metrics` 항목에 추가.
   - `AccuracyMetricsCollector`(가 있다면) 또는 equivalent에서 새 메트릭 이름 정의:
     ```
     dispatch.lane_usage.totals.dma
     dispatch.lane_usage.totals.te
     dispatch.lane_usage.max_concurrency.dma
     ...
     ```
2. **골든 리포트 재생성**
   - Stage 8 CLI 확장 이후 `run-cq --simulate` 또는 임시 스크립트로 골든 trace 실행 → `lane_usage` 값을 포함한 summary 덤프.
   - `workloads/golden/summaries/*.json` 갱신 + `git add`.
3. **정책 조정**
   - `workloads/golden/configs/*.json` 내 `accuracy_guard.metrics`에 새 메트릭을 자동 포함하는 로직 검토(현재 스크립트가 자동화되어 있다면 별도 변경 불필요).
   - 편차 제한은 기존 0.05 유지. 필요 시 lane-specific threshold 지원 옵션 도입 (백로그).
4. **CI 보고**
   - `cq_accuracy_report.json`가 새로운 필드를 보여주게 되며, GitHub Actions 아티팩트 내에서 확인 가능.
   - 문서(`docs/performance_simulator_refactoring_plan/project_board.md`, Stage 8 체크리스트) 업데이트.

## 5. 테스트 계획
| 유형 | 내용 |
|------|------|
| 단위 | `scripts.check_cq_accuracy`의 메트릭 파서 테스트 추가(새 키 감지, threshold 적용) |
| 통합 | golden 워크로드 하나에 대한 실행 후 `lane_usage` 비교가 PASS 하는지 확인 |
| 회귀 | 기존 골든 실행이 실패하지 않는지, 불필요한 메트릭이 누락될 경우 친절한 오류 메시지 추가 |

## 6. 리스크 & 완화
- **골든 갱신 후 CI 실패**: 새 필드가 누락되면 Accuracy Guard가 실패할 수 있으므로 문서와 PR 체크리스트에 "골든 재생성" 단계 명시.
- **정책 미래 확장**: 멀티 레인 구성이 추가되면 메트릭 수가 늘어남 → 자동 메트릭 탐색(딕셔너리 순회)으로 구현해 추후 레인 수 변화에도 대응.
- **CLI 미완성**: 실행 CLI 확장이 완료되기 전까지는 내부 스크립트를 사용해야 하므로, 문서에 임시 실행 명령(예: `python -m src.simulator.tools.run_cq_trace`)을 안내.

## 7. 후속 백로그 항목 제안
- `CQ-BG-007D`: `scripts.check_cq_accuracy`에 lane usage 메트릭 추가 및 golden summary 업데이트.
- `CQ-BG-007E`: `run-cq --simulate` CLI 도입 후 골든 재생성 자동화 스크립트 추가 (`make regenerate-goldens`).
- `CQ-BG-007F`: Accuracy Guard 정책 문서(`docs/performance_simulator_refactoring_plan/stage_plan_checklist.md`)에 lane usage 모니터링 기준 명시.

