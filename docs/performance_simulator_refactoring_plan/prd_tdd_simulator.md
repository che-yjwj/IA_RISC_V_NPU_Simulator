D & TDD: 성능 시뮬레이터 리팩토링 기반 개발 계획 (Spec-Driven Workflow)

## 1. Product Requirements Document (PRD)

### 1.1 목적
- **IR → ISA → Command Queue(CQ) → Simulator → HW** 파이프라인을 완성하여,
  - 기능 검증 (정상/에러 시나리오)
  - ISA 확장 효과 분석
  - 성능/경합 시나리오 평가
  를 가능하게 한다.  
- 기존 레포의 **이벤트 엔진, Accuracy Guard, 통계 인프라**는 그대로 활용한다.  

### 1.2 요구사항
- **정합성**: IR에서 HW 실행까지 trace ID로 역추적 가능해야 한다.  
- **추적성**: ISA 명세와 CQ 포맷이 단일 스펙에서 관리된다.  
- **확장성**: ISA opcode, CQ 필드, 자원 모델 추가 시 최소 수정으로 반영.  
- **재현성**: 동일 CQ 입력 → 동일 타임라인 결과(결정론적 실행).  
- **안전성**: 기존 ELF 실행 경로는 그대로 보존한다.  

### 1.3 범위
- ISA 정의 (`isa.yaml`)  
- CQ 스키마 (`cq.schema.json`)  
- IR 매핑 룰 (`rules/*.yaml`)  
- Dispatcher CQ consumer  
- Golden Test + Accuracy Guard 확장  

### 1.4 비범위
- CPU 사이클 정확 모델링 (stub 유지)  
- 고급 scheduling 알고리즘(HEFT, ML 기반)은 초기 범위 외  

### 1.5 성공 기준
- CQ 기반으로 GEMM + DMA 데이터 경로가 시뮬레이터에서 실행됨.  
- Conv 커맨드 파이프라인 확장은 백로그 이슈 `CQ-BG-004`에서 추적한다.  
- 동일 워크로드를 ELF vs CQ 입력으로 실행 시 ±15% 오차 이내.  
- ISA 추가 시 codegen/테스트/문서 자동 갱신(백로그 `CQ-BG-002`).  

---

## 2. Technical Design Document (TDD)

### 2.1 시스템 구조
```
[IR(Graph)] --(rules.yaml)--> [ISA Seq]
        |                          |
     isa.yaml             (CQ-BG-002)
        |                          v
        |---> dataclass -----> [ISA Instr]
                               |
[ISA Seq] --(isa_to_cq)--> [CQ.jsonl]
                               |
                          cq.schema.json
                               |
                           [Dispatcher]
                               |
                        [Event Engine]
                               |
                        [Summary/Trace]
```

### 2.2 핵심 모듈
- ISA Spec (`isa.yaml`): opcode, operand, latency, 자원 제약 정의  
- CQ Schema (`cq.schema.json`): 명령 포맷, deps, trace 필드 포함 (`sync` 필드 추가는 백로그 `CQ-BG-003`)  
- Dispatcher (CQ Consumer): CQ 엔트리를 읽어 자원 모델과 이벤트 엔진에 전달  
- Codegen: 명세에서 dataclass/validator 자동 생성  
- Testing: Unit/Integration/Golden 테스트 체계  

### 2.3 단계별 개발 로드맵
| 스테이지 | 기간 | 작업 | 산출물/백로그 |
|----------|------|------|---------------|
| 0 | 주0 | 리포 준비 & 가드레일 | 브랜치, CQ 디렉토리, `run-cq` CLI |
| 1 | 주1~2 | ISA/CQ 스펙 최소 정의 | `specs/isa.yaml`, `src/cq/cq.schema.json` |
| 2 | 주2~3 | CQ IO + 실행 골격 | `src/cq/io.py`, CLI `run-cq` |
| 3 | 주3~4 | Dispatcher 통합 & 기본 테스트 | `src/cq/dispatcher.py`, `tests/integration/test_cq_dispatcher.py` |
| 4 | 주4~6 | 자원/타이밍 모델링 | 백로그 `CQ-BG-003` (SPM/Bus/DMA/TE) |
| 5 | 주6~7 | Spec 기반 코드젠 | 백로그 `CQ-BG-002` |
| 6 | 주7~8 | IR→ISA, ISA→CQ 변환 | 백로그 `CQ-BG-005` (`src/cq/rules`, `src/cq/mapper.py`, `src/cq/generator.py`) |
| 7 | 주8~9 | Accuracy Guard & Golden | 백로그 `CQ-BG-006` |
| 8 | 주9+ | 스케줄/모델 확장 | 백로그 `CQ-BG-007` |
| 9 | 주9+ | 문서화/시각화 | 백로그 `CQ-BG-008` |

### 2.4 위험요소 & 대응
- 기존 경로 파손 → CLI 이중 모드 유지 (`run-elf`, `run-cq`)  
- 스펙 과도 확장 → 최소 subset에서 시작, 점진적 확장  
- 테스트 부족 → Accuracy Guard + Golden Test 강화  
- 성능 저하 → 이벤트 엔진 재사용, CQ wrapper 방식  
- 구현/문서 불일치 → 백로그 항목으로 명시하고 체크리스트와 교차 참조  

### 2.5 백로그 링크
- `CQ-BG-001`: 기존 ELF 실행 경로 회귀 테스트 자동화 및 결과 보존
- `CQ-BG-002`: ISA/CQ spec 기반 dataclass/codegen 파이프라인 도입 (`src/cq/spec.py`, `src/cq/adapter.py` 수동 정의 대체)
- `CQ-BG-003`: 자원/타이밍/경합 모델 구현 (SPM bank, Bus slice, DMA row latency, GEMM 근사 및 deadlock 감지)
- `CQ-BG-004`: Conv→GEMM 변환 및 ISA/워크로드 확장 (Conv opcode 추가, CQ workload 업데이트)
- `CQ-BG-005`: `rules/*.yaml` 정의 및 mapper/generator 구현으로 IR→ISA→CQ trace ID 체인 완성
- `CQ-BG-006`: Golden 워크로드 5종 및 Accuracy Guard diff 통합
- `CQ-BG-007`: 스케줄 정책(RR/EDF) 및 멀티 lane 모델링
- `CQ-BG-008`: ISA/CQ 레퍼런스 자동 생성 및 가시화(Gantt, Timeline CSV, 튜토리얼)
- 백로그 진행 현황은 `docs/performance_simulator_refactoring_plan/project_board.md` 칸반에서 관리한다.
