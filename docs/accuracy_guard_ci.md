# 정확도 가드 자동 검증 가이드

## 개요
정확도 가드는 시뮬레이션 결과 요약이 골든 데이터와 일치하는지 확인해 회귀를 빠르게 탐지한다. 아래 절차를 CI 파이프라인에 추가하면 Stage 5에서 확장한 지표(CPU/NPU 활용도, 대기 지표, 페치 지연 분위수)가 항상 기준값을 유지하는지 자동으로 확인할 수 있다.

## 로컬 점검 명령
```bash
python -m src.simulator.cli benchmark \
  --instructions 1 \
  --config ia_risc_v_npu/workloads/demos/accuracy_guard/configs/baseline.json
```
- CLI는 정확도 가드가 실패하면 종료 코드 1을 반환한다.
- `--output` 경로를 지정하면 비교 보고서를 JSON으로 저장할 수 있다.

## 골든 데이터 재생성 자동화
- `python -m scripts.regenerate_accuracy_golden`으로 데모 골든을 갱신할 수 있다.
- CI에서 골든을 업데이트할 필요는 없지만, 회귀 분석 후 수동으로 스크립트를 실행해 변경 사항을 커밋하는 워크플로를 권장한다.

## GitHub Actions 예시
```yaml
- name: Run accuracy guard benchmark
  run: |
    python -m src.simulator.cli benchmark \
      --instructions 1 \
      --config ia_risc_v_npu/workloads/demos/accuracy_guard/configs/baseline.json \
      --output /tmp/accuracy_summary.json
```
- 추가 시나리오를 검증하려면 config 목록을 돌면서 동일한 명령을 실행하면 된다.
- 출력 JSON은 아티팩트로 업로드해 비교 이력을 남길 수 있다.

## 보고서 통합 팁
- `jq '.accuracy_guard.metrics[] | select(.deviation != 0)' /tmp/accuracy_summary.json` 으로 편차가 발생한 지표만 추려낼 수 있다.
- CI 로그에 핵심 지표(`fetch_metrics.latency_p99`, `cpu_metrics.utilization`)를 출력해 추세를 모니터링하는 것을 권장한다.
