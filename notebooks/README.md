# Notebooks (Planned)

이 디렉터리는 Stage 6/7 시나리오를 실습하기 위한 Jupyter Notebook을 보관하기 위한 공간입니다.

## 권장 작성 지침
- 각 노트북에는 의존 패키지와 실행 방법을 첫 셀 또는 README에 명시하세요.
- 결과 비교를 위해 `docs/tutorials/scheduler_basics.md`에서 생성한 요약 JSON을 불러오도록 구조화하면 재사용성이 높습니다.
- 정확도 가드나 스케줄러 정책을 다루는 노트북은 관련 문서 링크(`docs/accuracy_guard_metrics.md`, `docs/npu_scheduler_followup.md`)를 포함하세요.

## 현재 노트북
- `basic_smoke_test.ipynb` – 스모크 테스트.
- `scheduler_metrics.ipynb` – 스케줄러 지표 비교.
- `accuracy_guard_analysis.ipynb` – 정확도 가드 분석.
- `cq_vs_elf_analysis.ipynb` – CQ vs ELF 비교.

노트북을 수정하거나 새로 추가할 때는 이 README와 `docs/tutorials/README.md`를 함께 업데이트해 주세요.
