# IA RISC-V + NPU Simulator: Final Documentation

## 1. Executive Summary
- 목적: RISC-V CPU와 NPU를 통합한 하이브리드 시스템을 빠르고 유연하게 분석할 수 있는 IA 기반 시뮬레이터 제공.
- 성과: RV64I 명령어 집합의 명령어 정확(IA) 엔진, 2-레벨 적응형 시뮬레이션, NPU/메모리 모델, CLI 기반 워크플로우 완성.
- 검증: 단위, 통합, 벤치마크, 정확도 테스트를 포함한 `pytest` 기반 테스트 스위트 구축. 주요 시나리오 자동화 완료.
- 성능: `pytest-benchmark`로 세부 연산 성능을 측정하고, CLI `benchmark` 커맨드로 전체 시뮬레이터 처리량(MIPS) 확인.

## 2. 시스템 아키텍처 개요
- **시뮬레이터 코어 (`src/simulator/main.py`)**: RISC-V 엔진, 버스, MMIO, NPU 모델을 묶어 비동기 루프(`asyncio`) 위에서 실행. `SimulationReport` 구조체로 실행 통계 반환.
- **RISC-V IA 엔진 (`src/risc_v/engine.py`)**: RV64I 명령어 집합을 명령어 정확 수준으로 구현. 분기, 메모리, ALU 명령어는 전용 모듈(`instructions/*`)에서 정의.
- **NPU 모델 (`src/npu/model.py`)**: 벡터 연산, GEMM, Scratchpad Memory(SPM) 연동. 버스/메모리 모델 (`src/simulator/memory.py`)과 직접 통신.
- **적응형 훅/컨트롤러**: `TimingHookSystem`과 `adaptive_controller`가 시뮬레이션 레벨 전환(Lev0↔Lev1)을 조율.
- **CLI (`src/simulator/cli.py`)**: `simulate`, `benchmark` 명령으로 프로그램 실행, 결과 저장, MIPS 측정과 같은 워크플로우를 캡슐화.
- **워크로드 & 유틸리티 (`workloads/`, `cnn_runtime.py`)**: CNN 레이어 기반 성능/정확도 검증을 위한 벤치마크 입력 생성.

## 3. 개발 산출물
- **설계 문서**: `docs/prd.md`, `docs/t032_accuracy_performance_report.md`, `docs/final_simulator_documentation.md`.
- **테스트 스위트**:
  - 단위 테스트: `tests/unit/` (엔진, 명령어, CLI, 메모리 등).
  - 통합 테스트: `tests/integration/` (CNN 워크로드, 전체 시뮬레이션).
  - 정확도 검증: `tests/verification/test_accuracy.py`.
  - 벤치마크: `tests/performance/test_performance.py` (`pytest-benchmark`).
- **CLI 워크플로우**: ELF 로더, 설정 파일(JSON) 파서, 결과 JSON 저장을 지원.

## 4. 사용 방법
1. **의존성 설치**
   ```bash
   cd ia_risc_v_npu
   pip install -r requirements.txt
   ```
2. **시뮬레이션 실행 (ELF 입력)**
   ```bash
   python3 -m src.simulator.cli simulate build/program.elf --config configs/example.json --output out/sim.json
   ```
   - `--config`: 실행 옵션(JSON) 지정. 예) `{"max_cycles": 200000}`.
   - `--output`: 결과 요약(JSON) 저장. 미지정 시 표준 출력 로그로만 제공.
3. **벤치마크 실행 (합성 프로그램)**
   ```bash
   python3 -m src.simulator.cli benchmark --instructions 200000 --output out/benchmark.json
   ```
   - `--instructions`: 합성 ADD 명령어 수. DRAM 용량(1MB) 이내로 자동 검증.
   - `--max-cycles`: 실행 사이클 상한. 기본 0(무제한).
   - 결과 JSON은 실행 시간, 실행 명령어 수, 계산된 MIPS 포함.
4. **테스트 실행**
   - 단위/통합 테스트: `python3 -m pytest tests/unit` / `python3 -m pytest tests/integration`
   - 정확도 테스트: `python3 -m pytest tests/verification/test_accuracy.py`
   - 벤치마크 테스트: `python3 -m pytest tests/performance/test_performance.py --benchmark-json performance_results.json`

## 5. 검증 & 품질 보증
- 전체 테스트 스위트는 `pytest.ini` 설정을 공유하며, `pytest-benchmark` 플러그인으로 미세 성능 변화를 추적.
- CNN 통합 테스트는 `workloads/cnn_workload.py`에서 생성한 파라미터화된 입력을 사용해 정상 동작을 확인.
- `Verification` 스위트는 DRAM 초기화, 레지스터 상태 비교를 통해 IA 엔진과 참조 모델의 동등성을 검증.
- CLI 테스트는 파일 입출력/예외 흐름을 모킹해 사용자 워크플로우를 재현.

## 6. 최종 벤치마크 결과 (2025-09-20)
- **`tests/performance/test_performance.py`** (명령 실행 평균 시간, `performance_results.json`):
  - ALU(Add/Sub/And/Or/Xor): 112~120 ns/호출.
  - 분기(JAL/JALR/BEQ/BNE): 112~216 ns/호출.
  - 메모리(LD/LW/SD/SW): 1.76~2.32 µs/호출.
  - NPU 벡터(VADD/VSUB/VMUL/VDIV, 1024 요소): 9.5~9.8 µs/호출.
- **CLI `benchmark` (합성 200k ADD, `benchmark_summary.json`)**:
  - 경과 시간 0.706 s, 실행 명령어 200,001, 산출 MIPS 0.28.
  - 적응형 후크/레벨 전환이 포함된 전체 루프 성능을 정량화.
- 결과 파일 위치:
  - `ia_risc_v_npu/performance_results.json`
  - `ia_risc_v_npu/benchmark_summary.json`

## 7. 한계 및 향후 과제
- 현재 MIPS는 목표(12-20 MIPS)에 도달하지 못함. 주요 병목은 Python 기반 버스/메모리 경로와 NPU 벡터 연산.
  - 제안: 버스·메모리 경로를 `numba` JIT 또는 C 확장으로 이전, NPU 연산을 `numpy` ufunc/BLAS로 위임, 이벤트 루프 병렬화 여부 검토.
  - 제안: 벤치마크 결과를 기준으로 최적화 백로그를 별도 이슈로 관리하고, MIPS 개선 시나리오(목표 vs 실측)를 문서화.
- Lev1(상세 모드)의 완전한 이벤트 기반 모델은 Skeleton 상태로 향후 구현 필요.
- ELF 로더는 `pyelftools` 의존. 배포 환경에는 해당 패키지 동봉 또는 설치 안내 필요.
- 성능 수집 자동화(GitHub Actions 등)와 장기적인 회귀 추적 대시보드 마련 권장.

## 8. 요약 체크리스트 (T033/T035)
- [x] 최종 아키텍처/사용법/품질 문서화.
- [x] `pytest-benchmark` 기반 세부 성능 측정 결과 확보.
- [x] CLI `benchmark` 명령으로 전체 처리량(MIPS) 리포트 생성.
- [x] 성능 결과 JSON 산출물 저장 및 문서 참조.
