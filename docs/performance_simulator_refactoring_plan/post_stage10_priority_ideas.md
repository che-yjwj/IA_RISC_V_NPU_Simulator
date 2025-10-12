# Post-Stage10 우선 작업 제안

Stage 10까지 모든 체크리스트를 완료한 이후, 다음 단계에서 고려할 만한 우선순위 아이디어 다섯 가지를 정리했다. 각 항목에는 현재 상태, 주요 목표, 추천된 액션을 간단히 포함한다.

## 1. `run-cq` 문서 확장
- **현황**: `docs/reference/cq_cli_reference.md:13`에 옵션 표 및 예제 제공이 TODO로 남아 있다.
- **목표**: `run-cq` 옵션/출력 스키마를 완전하게 정리해 신규 기여자가 CLI 사용법을 빠르게 익힐 수 있도록 한다.
- **추천 액션**
  - 플래그별 요약, 입력/출력 예시, Accuracy Guard 연동 흐름을 문서에 추가.
  - Stage9 문서(`docs/tutorials/cq_pipeline.md`)와 레퍼런스 간 링크를 정리해 일관성 확보.

## 2. TE_CONV2D ISA 회귀 테스트 보강
- **현황**: Stage10 계획에서 언급한 `tests/unit/test_isa_spec_conv.py`가 아직 미구현이다.
- **목표**: `load_isa_spec` 경로에 TE_CONV2D 필수/선택 피연산자 검증을 추가해 ISA 변경 시 회귀를 조기에 감지한다.
- **추천 액션**
  - `ia_risc_v_npu/tests/unit/test_cq_spec.py`를 참고해 Conv 전용 케이스를 분리 작성.
  - 누락/잘못된 피연산자에 대한 negative 테스트를 포함해 스펙 검증 강도를 높인다.

## 3. CQ 어댑터의 Conv 처리 개선
- **현황**: `build_execution_plan`은 DMA/TE_GEMM/FENCE만 지원하며 TE_CONV2D 명령이 직접 들어오면 미지원 오류가 발생한다 (`ia_risc_v_npu/src/src/cq/adapter.py:70` 근처).
- **목표**: Conv CQ가 GEMM으로 낮춰지지 않은 경우에도 어댑터가 graceful하게 처리하도록 확장해 향후 ISA 확장성을 보장한다.
- **추천 액션**
  - `TE_CONV2D_Operands`를 파싱해 내부적으로 GEMM 플랜을 구성하거나, Conv 전용 핸들러를 추가.
  - 관련 단위 테스트를 `ia_risc_v_npu/tests/unit/test_cq_adapter.py` 등에 추가해 회귀 방지.

## 4. Conv 워크로드 다양화
- **현황**: 기존 샘플/골든 자산(`workloads/cq/sample_conv.yaml`, `ia_risc_v_npu/workloads/golden/summaries/cq_conv_single.json`)은 stride/padding/dilation 기본값만 사용.
- **목표**: 다양한 Conv 파라미터(예: stride 2, dilation 2)를 포함한 추가 워크로드를 마련해 Accuracy Guard가 TE_CONV2D 확장 필드를 실제로 커버하도록 한다.
- **추천 액션**
  - 새로운 플랜/트레이스/골든 요약을 추가하고 `workloads/golden/manifest.py`에 등록.
  - 추가 워크로드를 `tests/integration/test_cli_run_cq.py` 회귀에 포함해 시뮬레이터가 새로운 패턴도 안정적으로 처리하는지 검증.

## 5. FidelityController TODO 처리
- **현황**: 시뮬레이터 초기화 경로에 `FidelityController` TODO 주석이 남아 있어 (`ia_risc_v_npu/src/src/simulator/main.py:242`), 실행 흐름이 명확히 정리되지 않았다.
- **목표**: Fidelity 컨트롤러를 구현하거나 제거해 시뮬레이터 설정이 명시적이고 관리 가능한 형태가 되도록 한다.
- **추천 액션**
  - 필요한 경우 최소 기능(값 클램프, 난수 시드 관리 등)을 제공하는 컨트롤러 클래스를 추가.
  - 사용하지 않을 계획이라면 TODO를 제거하고 대체 전략(설정 파일, 주석 등)을 명시해 문서화.
