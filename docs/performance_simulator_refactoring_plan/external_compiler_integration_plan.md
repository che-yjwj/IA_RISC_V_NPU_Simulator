# TVM/MLIR 연계 로드맵

## 1. 배경
- 시뮬레이터는 현재 **준비된 IR → ISA → CQ → 시뮬레이션** 구간을 담당하며, ONNX 모델로부터 IR을 생성하거나 고급 스케줄링을 수행하는 기능은 포함하지 않는다.
- 상위 계층(그래프 최적화, 타일링, 레이아웃 변환, 스케줄 탐색)은 TVM, MLIR 등 외부 컴파일러가 담당하는 것이 자연스러운 역할 분담이다.
- Stage 10까지 CQ 파이프라인이 정착했으므로, 외부 컴파일러와 연계해 엔드투엔드 워크플로를 준비할 시점이다.

## 2. 단기 계획 (1~2 스프린트)
- **IR 스키마 합의**
  - TVM/MLIR이 제공할 Conv/GEMM 타일 메타데이터를 `rules/*.yaml`이 소비할 수 있도록 키/구조 정의서 초안 작성.
  - 필요한 필드를 `docs/specs` 혹은 신규 문서에 명시하고 리뷰 사이클 운영.
- **프로토타입 컨버터 작성**
  - 고정된 예시 그래프(ONNX Conv→GEMM 등)를 TVM/MLIR에서 하향 변환한 뒤, IR JSON/YAML을 시뮬레이터의 `generate_command_queue`가 읽을 수 있는 형태로 매핑하는 스크립트 추가.
  - 실패 시그널과 로그 포맷을 통일해 `scripts/` 하위에 배치.
- **테스트 & Accuracy Guard 연동**
  - 변환된 CQ를 이용해 `pytest ia_risc_v_npu/tests/integration/test_cli_run_cq.py` 기반의 회귀 테스트 케이스를 추가.
  - 새로운 CQ 요약을 Accuracy Guard 골든에 등록하고 편차 한계를 검증.
- **문서 업데이트**
  - `docs/tutorials/cq_pipeline.md`에 외부 컴파일러 연계 플로우(ONNX→TVM/MLIR→IR→CQ)를 추가하고 재현 명령을 정리.

## 3. 장기 로드맵 (분기 단위)
- **엔드투엔드 파이프라인 확보**
  - ONNX → TVM/MLIR → 도메인 맞춤 IR → CQ → 시뮬레이터 → Accuracy Guard로 이어지는 자동 파이프라인을 GitHub Actions 또는 내부 CI에 구축.
  - IR→CQ 변환 실패, 시뮬레이터 편차 초과 등 주요 이벤트에 대한 알림 및 아티팩트 보존 전략 수립.
- **스케줄링 연구 연동**
  - TVM meta-scheduler, MLIR polyhedral 패스, 또는 외부 연구용 스케줄러가 산출하는 결과를 CQ 레벨에서 비교 실험하고, `dispatch.timeline`·`lane_usage` 지표와 연계한 벤치마크 셋을 정의.
  - 정책 파라미터를 시뮬레이터 config(`cq.dispatcher.policy`, lane limits 등)로 자동 주입하는 인터페이스 구현.
- **모델 정밀도 보강**
  - 외부 컴파일러가 추정하는 FLOP/메모리 교환 비용과 시뮬레이터의 자원 모델을 캘리브레이션하여, Accuracy Guard 기준(±15% → ±10% 등) 조정 가능성을 탐색.
- **툴체인 패키징**
  - TVM/MLIR 빌드, IR 변환 스크립트, CQ 시뮬레이터 실행을 하나의 Docker 이미지 또는 devcontainer로 묶어 재현성을 높인다.

## 4. 연계 시 고려 사항
- **IR 필드 확장**: `CommandQueue`와 `trace` 구조에 스케줄 ID, 비용, 태그를 수용할 확장 포인트를 확보하고 필요 시 `cq.schema.json` 업데이트.
- **구성 파라미터 주입**: 외부 스케줄링 결과가 가정한 하드웨어 리소스를 `AdaptiveSimulator` config로 쉽게 전달할 수 있도록 CLI 플래그/JSON 스키마를 확장.
- **디버깅 지원**: 변환된 IR, CQ, 스케줄 메타데이터를 단계별로 덤프하는 옵션을 추가해 연계 오류를 추적 가능하게 한다.

## 5. 리스크 및 대응
- **스킴 불일치**: TVM/MLIR 버전 변화로 IR 필드가 달라질 수 있으니, 어댑터에서 스키마 검증과 명시적 오류 메시지를 제공한다.
- **성능 편차 증가**: 외부 스케줄이 새로운 패턴을 생성해 Accuracy Guard가 실패할 수 있으므로, 편차 확대 시 대시보드/리포트를 통해 원인을 자동 수집한다.
- **의존성 관리**: TVM/MLIR 빌드 시간이 길어질 수 있으므로, 미리 컴파일된 패키지 또는 캐시 전략을 계획한다.

## 6. 다음 액션 아이템 요약
1. IR 필드 정의서 및 어댑터 요구사항 초안 작성.
2. 샘플 ONNX 그래프를 이용한 TVM/MLIR → IR → CQ 변환 프로토타입 구현.
3. 변환된 CQ에 대한 통합 테스트 및 Accuracy Guard 검증 추가.
4. 튜토리얼/문서에 외부 컴파일러 연계 절차 반영.
