# RISC-V NPU Simulator PRD - XNPU ISA

## ISA 확장 (custom-0, opcode=0x0B)
### 명령어 그룹
- LDMA/SDMA: DRAM↔SPM 전송
- MMA: 행렬곱/Conv
- VEC: elementwise
- CONF: 설정
- BARR: 동기화
- PREF: 프리페치

### 인코딩
- R형, I형 혼용
- funct7, funct3로 세분화

### Descriptor 구조체
- DMA: src_pa, dst_spm, bytes, stride, count
- MMA: a_spm, b_spm, c_spm, m,n,k, lda/ldb/ldc

### CSR & MMIO
- CSR: xnpu_cfg, xnpu_stat, xnpu_qbase, xnpu_qptr, xnpu_perf*
- MMIO: doorbell, status, spm window
