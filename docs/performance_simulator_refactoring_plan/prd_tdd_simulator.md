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
- CQ 기반으로 Conv→GEMM + DMA 동작이 시뮬레이터에서 실행됨.  
- 동일 워크로드를 ELF vs CQ 입력으로 실행 시 ±15% 오차 이내.  
- ISA 추가 시 codegen/테스트/문서 자동 갱신.  

---

## 2. Technical Design Document (TDD)

### 2.1 시스템 구조
```
[IR(Graph)] --(rules.yaml)--> [ISA Seq]
        |                          |
     isa.yaml                  isa_codegen
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
- CQ Schema (`cq.schema.json`): 명령 포맷, deps, trace, sync 필드 포함  
- Dispatcher (CQ Consumer): CQ 엔트리를 읽어 자원 모델과 이벤트 엔진에 전달  
- Codegen: 명세에서 dataclass/validator 자동 생성  
- Testing: Unit/Integration/Golden 테스트 체계  

### 2.3 단계별 개발 로드맵
| 단계 | 기간 | 작업 | 산출물 |
|------|------|------|--------|
| 1 | 주1~2 | ISA/CQ Spec 최소 정의 | `isa.yaml`, `cq.schema.json` |
| 2 | 주2~3 | CQ IO + Dispatcher consumer | `dispatcher_cq.py` |
| 3 | 주3~4 | 기본 Test & Golden 비교 | ELF vs CQ 결과 리포트 |
| 4 | 주4~5 | Codegen 도입 | dataclass/validator 자동 생성 |
| 5 | 주5~6 | Dispatcher 확장 | bank conflict, bus contention |
| 6 | 주6~7 | Docs 자동화 | ISA/CQ Reference Markdown |
| 7 | 주8+ | ISA 확장, Scheduling 옵션 | 추가 opcode, RR/EDF |

### 2.4 위험요소 & 대응
- 기존 경로 파손 → CLI 이중 모드 유지 (`run-elf`, `run-cq`)  
- 스펙 과도 확장 → 최소 subset에서 시작, 점진적 확장  
- 테스트 부족 → Accuracy Guard + Golden Test 강화  
- 성능 저하 → 이벤트 엔진 재사용, CQ wrapper 방식  


