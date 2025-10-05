# CQ Adaptation Specification

## gemm_dense
- ISA operation: `TE_GEMM`
- CQ sequence: `DMA_2D` -> `TE_GEMM` -> `DMA_2D`
- Description: Standard GEMM tiled load/compute/store pipeline.

Operands:
- `matrix_a`: `dram://inputs`
- `matrix_b`: `dram://weights`
- `matrix_out`: `dram://outputs`

Schedule Steps:
1. DMA from DRAM inputs to SPM tile (`dram://inputs` → `spm://tile0`).
2. GEMM on SPM tile using DRAM weights; result kept in `spm://tile0`.
3. DMA from SPM tile to DRAM outputs.
