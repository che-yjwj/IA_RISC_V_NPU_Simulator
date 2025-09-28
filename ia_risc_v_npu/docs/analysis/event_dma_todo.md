# Event-Driven DMA Follow-up Tasks

## 1. NPUCluster 이벤트 스케줄러 적용
- [x] DMA 요청 큐 도입: `ClusterTask` 제출 시 입력/출력 DMA를 `DeferredDMA` 객체로 저장
- [x] 채널별 우선순위 정의: 동일 시각일 경우 입력→출력→기타 순서로 정렬
- [x] `flush_deferred_dma(now)` 구현: 현재 시각 이전 요청을 실제 `Bus.request`로 재생

## 2. 시뮬레이터 루프 통합
- [x] `AdaptiveSimulator` 실행 루프에서 각 이벤트 처리 후 DMA flush 호출
- [x] CPU fetch/메모리 요청과의 결정성 확인 (테스트 or 로그)
- [x] 기존 CNN/NPU 워크로드 재실행으로 겹침 지표 수집

## 3. 검증 및 문서화
- [ ] 프로파일링 스크립트 결과 갱신 및 비교(virtual vs real)
- [x] 단위/통합 테스트 추가 또는 기존 테스트 보강
- [ ] PR 요약 및 문서 업데이트 (설계/README 등 필요한 부분)
