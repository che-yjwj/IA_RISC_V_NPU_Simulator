# Documentation Index

## Overview
- `RISC_V_NPU_Simulator_Refactoring_Plan.md` – 단계별 리팩토링 로드맵.
- `RISC_V_NPU_Simulator_Refactoring_Plan_Review.md` – 리뷰 기록 및 결정 사항.
- `performance_simulator_refactoring_plan` – 성능 시뮬레이터 계획 초안.

## Validation & Calibration
- `validation_calibration.md` – 테스트/벤치마크 플레이북.
- `accuracy_guard_metrics.md`, `accuracy_guard_ci.md` – 정확도 가드 지표 정의와 CI 연계.
- `config_parameter_management.md` – 설정 검증 및 샘플 구성 가이드.
- 유지 보수 도구: `python -m scripts.check_specs_index` – `specs/README.md`와 파일 목록 일치 여부 검증 (CI: `.github/workflows/specs_check.yml`).

## Scheduler & CQ
- `npu_scheduler_followup.md` – 스케줄러 후속 로드맵.
- `cq_adaptation_spec.md` – CQ 입력 계층 사양.

## Tutorials & Notebooks
- 튜토리얼 모음: `docs/tutorials/README.md`
- 노트북 공간: `notebooks/README.md`

## Configuration Samples
- Calibration baseline: `workloads/calibration/configs/rr_baseline.json`
- Priority tuning: `workloads/calibration/configs/priority_tuning.json`
- Accuracy guard demo: `workloads/demos/accuracy_guard/configs/`
- Calibration overview: `workloads/calibration/README.md`

## External Integration
- `NPU_Simulator_Simulink.md`, `simulink_docs/` – 시뮬링크 통합 자료.

> Specs 디렉터리의 스키마/정의는 `specs/README.md`에서 요약합니다.
