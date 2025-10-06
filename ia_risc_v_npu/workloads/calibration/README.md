# Calibration Scenarios

## rr_baseline.json
- 정책: `npu.policy = "rr"`
- 용도: 라운드 로빈 스케줄링 성능 기준선 측정.
- 실행 예시:
  ```bash
  python -m src.simulator.cli benchmark \
    --instructions 1000 \
    --config ia_risc_v_npu/workloads/calibration/configs/rr_baseline.json \
    --output /tmp/rr_summary.json
  ```

## priority_tuning.json
- 정책: `npu.policy = "priority"`
- 용도: 우선순위 기반 스케줄러 튜닝 및 NPU 대기 지표 비교.
- 실행 예시:
  ```bash
  python -m src.simulator.cli benchmark \
    --instructions 1000 \
    --config ia_risc_v_npu/workloads/calibration/configs/priority_tuning.json \
    --output /tmp/priority_summary.json
  ```

## 향후 추가 예정
- WFQ 정책 샘플 (Stage 6)
- EDF 정책 샘플 (Stage 6)

## 참고
- 추가 설정 작성 시 `docs/config_parameter_management.md`를 참고하여 검증 절차를 따라주세요.
- 검증/보정 워크플로는 `docs/validation_calibration.md`에 정리되어 있습니다.
