# Configuration & Parameter Management Guide

## 1. Validation Pipeline
- 중앙 진입점: `src.simulator.config.validate_simulator_config` (JSON dict → 보정된 config).
- 필드별 검증기:
  - `_validate_cache_section`, `_validate_bus_section`, `_validate_dram_section`
  - `_validate_npu_section` (추후 정책 확장 시 업데이트)
  - `_validate_accuracy_guard_section`, `_validate_logging_section`
- 신규 필드 추가 시 단계:
  1. `default_simulator_config()`에 기본값 정의.
  2. `_validate_*` 함수 작성 또는 확장.
  3. `validate_simulator_config`에서 키를 허용하도록 분기 추가.
  4. 단위 테스트(`tests/unit/simulator/test_config_validation.py`) 케이스 추가.

## 2. Config Layout & Samples
- 기본 JSON 샘플은 `ia_risc_v_npu/workloads/` 하위에 위치.
  - `workloads/demos/accuracy_guard/configs/` – 정확도 가드 데모.
  - `workloads/calibration/configs/` – 스케줄 정책/Tuning 비교.
  - `workloads/profiling/configs/` – 버스/DRAM 프로파일링.
- 새 시나리오를 추가할 때는 `workloads/<category>/configs/`에 JSON을 배치하고 README 또는 `docs/validation_calibration.md`에서 참조.

## 3. Adapter Patterns
- CLI는 JSON 파일을 직접 로드 (`src.simulator.cli.load_config`).
- YAML 등 다른 포맷을 허용하려면 내부에서 `json.dumps` → `json.loads` 변환을 거치는 어댑터 모듈을 작성해 `validate_simulator_config`에 전달.
- 어댑터 작성 시 에러 메시지와 스키마 버전 호환성을 유지할 것.

## 4. Recommended Workflow
1. **초안 작성**: 새로운 설정을 `workloads/<category>/configs/*.json`으로 작성.
2. **검증 실행**: `python -m src.simulator.cli simulate ... --config <file>` 또는 `benchmark` 서브커맨드로 로드.
3. **테스트 연동**: 필요한 경우 테스트 케이스에서 `load_config` 호출로 재사용.
4. **문서 업데이트**: 관련 문서를 `docs/validation_calibration.md`, `docs/accuracy_guard_metrics.md` 등에 추가.

## 5. Cross-References
- Stage 7 전략: `docs/validation_calibration.md`.
- 정확도 가드 가이드: `docs/accuracy_guard_metrics.md`, `docs/accuracy_guard_ci.md`.
- 스케줄러 후속 로드맵: `docs/npu_scheduler_followup.md`.

> 구성 파일은 항상 JSON 기반을 유지하고, 어댑터는 내부적으로만 포맷 변환을 처리한다.
