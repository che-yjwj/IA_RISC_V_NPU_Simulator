# Stage 8 Follow-up · `run-cq` Trace 실행/리포트 확장 설계 초안

> ✅ 1차 구현 (`--simulate`) 완료 — `src/simulator/cli.py`에 반영, `tests/integration/test_cli_run_cq.py::test_run_cq_simulate_includes_execution`로 검증함. 아래 메모는 추가 기능/문서화를 위한 참고용입니다.

## 1. 배경 & 목적
- 현재 `python -m src.simulator.cli run-cq`는 CQ JSONL 구조 검증과 ISA 매핑 요약만 출력하며, Stage 8에서 확장한 디스패처 정책·레인 통계는 CLI 결과로 확인할 수 없다.
- Stage 8 산출물(정책 선택기, `lane_limits`, `dispatch.lane_usage`)을 검증/디버깅하려면 CQ trace를 시뮬레이터 경로로 실행해 실행/리소스 통계를 JSON으로 노출하는 CLI가 필요하다.
- 목표: 기존 `run-cq` 명령에 시뮬레이션 옵션을 추가(또는 별도 서브커맨드 제공)하여 CQ trace 실행 및 실행 요약(플랜, 디스패처, 실행 리포트)을 기록한다.

## 2. 요구사항 정리
| 구분 | 상세 |
|------|------|
| 기능 | `run-cq`가 `AdaptiveSimulator.run_cq_trace`를 호출해 CQ trace 실행 후 JSON 요약( plan/dispatch/execution/lane_usage )을 생성 |
| 옵션 | `--simulate` 플래그 (또는 `--mode {validate,simulate}`) + 기존 `--cq-policy`, `--cq-lane-limit` 적용 |
| 출력 | 기본 요약(현재 필드) + `plan_summary`, `dispatch`, `execution`, `metadata` 확장. `dispatch.lane_usage` 포함 |
| Config | `--config` 파일과 CLI 플래그를 병합해 시뮬레이터 인스턴스 생성. Accuracy Guard 옵션 지원 여부 검토 |
| 로그 | 기본 `run-cq`와 동일한 로깅 구조 유지, verbose 시 실행 단계 TRACE 선택 |
| 테스트 | 단위 테스트(옵션 파싱/환경 설정), 통합 테스트(CQ 실행 + 출력 구조 검증), 회귀 테스트(기존 validate 모드 유지) |

## 3. CLI 동작 흐름 초안
```
run-cq TRACE \
  [--simulate] \
  [--output FILE] \
  [--config CONFIG.json] \
  [--cq-policy POLICY] \
  [--cq-lane-limit LANE=N]...
```
1. 기존 `_setup_environment` 재사용 → config 로드 + CLI override.
2. `--simulate`가 지정되면:
   - `load_cq_trace` → `AdaptiveSimulator(config)` → `load_cq_tensors` (추가 플래그? TBD)
   - `simulator.run_cq_trace(queue)` 호출
   - 결과 요약을 `summary["cq_execution"]` 또는 `summary.update()` 형태로 합산
   - `accuracy_guard` 구성값이 있으면 `scripts.check_cq_accuracy`와 동일한 비교 함수 호출 고려 (후속 단계)
3. `--simulate` 미지정 시 기존 validate 경로 유지 (default backward compatible).

### 플래그/하위 옵션
- `--simulate` (bool) : 실행 모드 전환
- `--simulate-output KEY` (TBD) : 출력 파일 구조 제어 (예: `full`, `dispatch-only`)
- `--load-tensors PATH` (옵션) : 시뮬레이션에 필요한 초기 텐서 데이터를 JSON/NPY로 로드하는 기능 (첫 단계에서는 스텁 or 향후 백로그로 분리)
- `--compare-elf PATH` (백로그) : `compare_cq_vs_elf`를 호출해 ELF 대비 정확도 비교 (Stage 9 이후)

## 4. 출력 스키마 변화 제안
```jsonc
{
  "status": "validated" | "simulated",
  "command_count": ...,
  ...
  "cq_execution": {
    "plan_summary": { "dma": 2, "gemm": 1, "fence": 0 },
    "dispatch": {
      "executed": 5,
      "completed": [...],
      "rejected": [...],
      "queue_wait": {...},
      "lane_usage": {
        "totals": {"dma": 3, "te": 1},
        "max_concurrency": {"dma": 2, "te": 1}
      }
    },
    "execution": {
      "executed": [...],
      "count": {...},
      "estimate_cycles": ...,
      "dma_cycles": ...,
      "dma_bytes": ...,
      "skipped": [...]
    },
    "metadata": {...},  // run_cq_trace plan metadata
    "config": { "policy": "rr", "lane_limits": {"dma":2,...} } // optional echo
  }
}
```
- `status` 값은 `simulate` 모드에서 `"simulated"`로 업데이트.
- `cq_execution` 키 하위에 실행 관련 정보를 모아 `run-cq` 기존 요약과 이름 충돌 최소화.

## 5. 구성/리소스 고려
- 기본 config와 CLI override를 `validate_simulator_config`에 전달하므로 Stage 8에서 도입한 검증 로직 활용 가능.
- Accuracy Guard 연계는 초기에는 off(스텁) 처리 후 Stage 7 확장과 통합.
- 텐서 로딩은 초기에는 필수 아님. 회귀 테스트와의 연계는 추후 Stage 8~9 백로그에서 다룸.

## 6. 테스트 전략
1. **Unit**
   - `_setup_environment`가 `--simulate`/`--cq-policy`/`--cq-lane-limit`를 병합하는지 확인 (`test_cli_cq_overrides` 확장).
   - 새 옵션 파서(`--simulate`) 동작 검증.
2. **Integration**
   - `tests/integration/test_cli_run_cq.py`: `--simulate` 실행으로 생성된 요약에 `cq_execution` 키와 `lane_usage`가 존재하는지 검증.
   - 실패 케이스 (예: 실행 중 예외) 핸들링 테스트.
3. **Regression**
   - 기존 `run-cq` 호출이 출력 형식을 변경하지 않는지 확인 (`--simulate` 미사용).
4. **Performance (추후)**
   - 골든 워크로드에 `run-cq --simulate`를 적용해 Accuracy Guard/시간 측정을 통합 (Stage 8.1 백로그).

## 7. 리스크 & 완화
| 리스크 | 완화 |
|--------|------|
| CQ trace 실행에 필요한 입력 텐서 부족 | 최초 릴리스에서 워크로드가 자체적으로 텐서를 로드하도록 제한, CLI에는 친절한 에러 메시지 제공 |
| 출력 JSON 증가로 기존 스크립트 호환성 문제 | 새 필드를 별도 `cq_execution` 블록에 넣어 하위 호환 유지 |
| 실행 시간이 길어지는 경우 | `--simulate`를 opt-in으로 두어 기본 경로 영향 최소화; 향후 `--max-cmds` 같은 샘플링 옵션 검토 |

## 8. 후속 백로그 제안
- `CQ-BG-007A`: `run-cq --simulate` CLI 구현 + 테스트 + 문서화.
- `CQ-BG-007B`: `compare_cq_vs_elf`/Accuracy Guard 통합 (골든 리포트에 lane usage 반영).
- `CQ-BG-007C`: CLI 텐서 로딩/리스타트 지원 (`--tensor-config`, `--load-state` 등).
- 문서 업데이트: `docs/tutorials/cq_pipeline.md`, `workloads/cq/README.md` CLI 사용법 추가.

## 9. 일정 가이드
1. 설계 검토 & 이슈 등록 (0.5d)
2. CLI/시뮬레이터 통합 구현 & 단위 테스트 (1.5d)
3. 통합 테스트 + 문서/예제 갱신 (0.5d)
4. 추가 골든/Accuracy Guard 연결(옵션) (1d, 백로그)
