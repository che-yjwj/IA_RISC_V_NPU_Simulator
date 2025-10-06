# Scheduler Comparison Tutorial

NPU 스케줄러 정책이 시뮬레이션 결과에 미치는 영향을 살펴보는 튜토리얼입니다.

## 1. 테스트 준비
- 샘플 설정:
  - 라운드 로빈: `ia_risc_v_npu/workloads/calibration/configs/rr_baseline.json`
  - 우선순위: `ia_risc_v_npu/workloads/calibration/configs/priority_tuning.json`
- 두 설정 모두 accuracy guard가 비활성화되어 있어 순수한 성능 지표 비교에 적합합니다.

## 2. 벤치마크 실행
```bash
for config in rr_baseline priority_tuning; do
  python -m src.simulator.cli benchmark \
    --instructions 1000 \
    --config ia_risc_v_npu/workloads/calibration/configs/${config}.json \
    --output /tmp/${config}_summary.json
done
```

## 3. 결과 비교
```bash
for config in rr_baseline priority_tuning; do
  echo "=== ${config} ==="
  jq '. | {mips, npu_metrics: {utilization: .npu_metrics.utilization, avg_wait: .npu_metrics.avg_wait_cycles}}' \
    /tmp/${config}_summary.json
done
```

- `npu_metrics.utilization`이 높을수록 NPU가 적극적으로 사용된다는 의미입니다.
- `npu_metrics.avg_wait_cycles`는 정책별 대기 시간 차이를 보여줍니다.

## 4. 확장 아이디어
- Stage 6에서 도입 예정인 WFQ/EDF 정책 설정을 동일한 패턴으로 추가해 비교 결과를 누적하세요.
- Accuracy guard를 활성화한 설정과 비교하여 정책 변경이 정확도 기준에 어떤 영향을 미치는지 검증할 수 있습니다.
- 결과 요약을 CSV 또는 노트북으로 가져와 시각화하면 추세 파악이 더욱 쉬워집니다.
