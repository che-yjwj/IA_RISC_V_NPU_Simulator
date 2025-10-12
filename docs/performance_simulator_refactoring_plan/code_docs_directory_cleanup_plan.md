# 코드/문서 디렉터리 정비 계획

## 1. 목적
- 루트 `workloads/`(CQ 샘플 중심)와 패키지 내부 `ia_risc_v_npu/workloads/`(Accuracy Guard·골든·생성 스크립트)를 명확하게 구분해 혼동을 줄인다.
- `ia_risc_v_npu/src/src` 형태의 중첩 `src` 디렉터리를 정리할 방안을 마련해 코드 가독성을 높인다.
- 루트 `docs/`와 패키지 내부 `ia_risc_v_npu/docs/`의 역할을 정의해 문서 탐색성을 개선한다.
- 문서와 코드에서 각 디렉터리의 역할을 일관되게 설명하고, 향후 확장을 위한 구조를 마련한다.

## 2. 현재 상태
- 루트: `workloads/cq/` 단일 하위 디렉터리로 Stage 7~10에서 생성한 CQ YAML/JSONL 샘플이 위치.
- 패키지 내부: `ia_risc_v_npu/workloads/` 아래 calibration, golden, generators 등 Accuracy Guard와 시뮬레이터 실행에 필요한 자산이 존재.
- 코드 패키지는 `ia_risc_v_npu/src/src` 구조로 구성되어 있으며 `from src.cq ...` 임포트가 중첩된 `src` 디렉터리에 의존.
- 문서는 루트 `docs/`(리팩토링 플랜, 튜토리얼 등)와 패키지 내부 `ia_risc_v_npu/docs/`(분석/결과 리포트 등)로 분산돼 있으나 역할 구분이 명시적이지 않음.
- README나 튜토리얼에서 두 위치의 관계가 명시적으로 설명되지 않아 기여자 입장에서 혼동 가능성이 있음.

## 3. 정비 계획
1. **디렉터리 구조 정리**
   - 루트 `workloads/`는 향후 CQ 실험 자산을 모으는 “샘플/데모” 용도로 유지.
   - `ia_risc_v_npu/workloads/`는 “패키지 배포 자산 및 Accuracy Guard 리소스”로 정의.
   - 루트에 README를 추가해 목적을 설명하고, 내부 자산에 대한 링크를 제공.
2. **문서 업데이트**
   - `README.md` 혹은 `docs/tutorials/cq_pipeline.md`에 두 디렉터리의 역할과 대표 파일을 설명하는 절을 추가.
   - Stage별 계획 문서(`docs/performance_simulator_refactoring_plan/stage_plan_checklist.md`)에 디렉터리 사용 규칙을 기록.
3. **코드 참조 점검**
   - 테스트 및 스크립트에서 상대 경로를 사용하는 부분(`tests/integration/test_cli_run_cq.py`, `scripts/check_cq_accuracy`)을 검토해 구조 변경과 충돌이 없는지 확인.
4. **추가 자산 배치 규칙 정의**
   - 새로운 CQ 샘플은 루트 `workloads/cq/`에, Accuracy Guard 골든/생성 스크립트는 패키지 내부로 추가하도록 CONTRIBUTING 가이드에 명시.
5. **중첩 `src` 구조 개선 조사**
   - `pyproject.toml` 및 패키징 설정을 검토해 `ia_risc_v_npu/src/src` 중첩 구조가 필요한지 확인.
   - 가능하다면 패키지 루트를 `ia_risc_v_npu/src`로 평탄화하고, 임포트 경로 및 설치 스크립트를 업데이트.
   - 평탄화가 어려울 경우 문서에 중첩 구조 이유와 개발 환경에서의 설정 방법을 명시.
6. **문서 디렉터리 역할 명확화**
   - 루트 `docs/`를 “프로젝트 운영 및 설계 문서”, `ia_risc_v_npu/docs/`를 “사용자 가이드/분석 리포트”로 명시.
   - 두 위치에 README 또는 인덱스 파일을 추가해 포함 문서와 목적을 소개.
   - 메인 README에서 문서 위치 차이와 접근 경로를 안내.

## 4. 예상 산출물
- `workloads/README.md` 갱신 혹은 신규 작성.
- 메인 README 및 튜토리얼 문서 업데이트.
- 경로 재배치가 필요한 경우 관련 스크립트/테스트 수정 PR 작성.
- `pyproject.toml` 패키징 설정 검토 보고 및 필요 시 `src` 디렉터리 구조 개선 PR.
- `docs/`와 `ia_risc_v_npu/docs/`에 역할 설명 README 또는 인덱스 문서 추가.

## 5. 후속 단계
- 정비 계획 승인 후, PR 단위로 디렉터리 README 및 문서 수정 진행.
- 구조 변경이 필요한 경우(예: CQ 샘플을 `workloads/cq/samples/`로 이동)에는 Accuracy Guard와 테스트 영향도를 먼저 검증한 뒤 적용.
- `src` 구조 변경과 관련한 패키징 테스트(로컬 설치, CI 빌드)를 수행해 회귀 여부를 확인.
- 문서 역할 구분 후, 신규 문서를 작성할 때 어느 디렉터리를 사용할지에 대한 가이드라인을 CONTRIBUTING에 반영.
