# Stage 10 — Conv→GEMM Pipeline Expansion

## 1. Goal
- Introduce a convolution opcode into the baseline ISA and map Conv IR nodes into CQ traces that reuse the GEMM execution path.
- Provide runnable samples (plan YAML, CQ JSONL, golden summary) that exercise the end-to-end Conv→GEMM transformation through `run-cq --simulate`.
- Ensure documentation, automation scripts, and tests cover the new op so Stage 4–9 assets remain coherent.

## 2. Deliverables
| Workstream | Deliverable | Files/Tools |
|------------|-------------|-------------|
| ISA Spec | Updated `specs/isa.yaml` with `TE_CONV2D` operands, regenerated dataclasses | `scripts/generate_cq_models.py`, `src/cq/generated/*`, `docs/reference/isa_cq_reference.md` |
| Mapping | Conv IR fixture + mapping rule that emits GEMM-friendly CQ commands | `src/cq/rules/conv.yaml`, `src/cq/mapper.py`, `tests/unit/test_cq_mapper_conv.py` |
| CQ Assets | Sample YAML/JSONL workload + golden summary with dispatcher metrics | `workloads/cq/sample_conv.yaml`, `workloads/cq/sample_conv.jsonl`, `workloads/golden/*` |
| Simulator | Execution path recognises Conv-derived GEMM commands and records lane usage | `src/simulator/main.py`, `src/cq/adapter.py` |
| Docs & CLI | Tutorial/CLI updates noting Conv support and regeneration steps | `docs/tutorials/cq_pipeline.md`, `docs/reference/cq_cli_reference.md`, `workloads/cq/README.md` |

## 3. Task Breakdown
1. **ISA & Codegen**
   - Extend `specs/isa.yaml` with `TE_CONV2D` + operand schema (padding, stride, dilation placeholders).
   - Run `python -m src.scripts.generate_cq_models` and `python -m src.scripts.generate_isa_cq_reference` to refresh generated artifacts.
   - Add validation tests for the new operands (`tests/unit/test_isa_spec_conv.py`).
2. **IR→CQ Mapping**
   - Finalise `rules/conv.yaml` to cover load/compute/store trio with trace metadata.
   - Provide sample IR fixture JSON/YAML and unit tests asserting the GEMM-emitted CQ matches expectations.
   - Ensure mapper gracefully errors when Conv operands are missing (negative test).
3. **Simulator Integration**
   - Confirm dispatcher `lane_for_command` classifies `TE_CONV2D` as `te` lane (extend helper if necessary).
   - Update `_CQActionExecutor` / plan builder so Conv emits GEMM actions or add a dedicated Conv handler.
   - Expand integration tests (`tests/integration/test_cli_run_cq.py`) to include Conv sample with `--simulate`.
4. **Workloads & Golden**
   - Author `workloads/cq/sample_conv.yaml` + generated `.jsonl`.
   - Add golden config/summary under `workloads/golden/conv_*` ensuring Accuracy Guard captures new metrics.
   - Update `scripts.check_cq_accuracy` fixtures if additional opcodes appear.
5. **Documentation & Tutorials**
   - Extend CQ tutorial with a Conv walkthrough snippet and mention timeline export compatibility.
   - Update project board/checklist to mark CQ-BG-004 stages, and add regeneration notes for Conv assets.
   - Provide Plotly notebook cell demonstrating Conv vs GEMM comparison if time permits.

## 4. Timeline & Milestones
- Week 1: ISA spec / codegen refresh + mapper unit tests.
- Week 2: Simulator integration + Conv CQ workload generation.
- Week 3: Golden summaries + CLI/tutorial documentation refresh.
- Week 4: Regression suite & Accuracy Guard alignment, close CQ-BG-004.

## 5. Dependencies
- Existing GEMM/DMA execution path (Stage 3–8) for reuse of compute & data movement logic.
- Codegen scripts from Stage 5 (`generate_cq_models.py`) and Stage 9 doc automation.
- Accuracy Guard infrastructure (Stage 7) for new golden baseline.

## 6. Risks & Mitigations
- **Operand explosion**: Conv parameters (padding/stride/dilation) can complicate validation — start with minimal fields, clearly mark TODOs for advanced attributes.
- **Golden drift**: Conv workloads may introduce longer runtimes — keep sample tensor sizes small and document expected cycle counts.
- **Scheduler mismatch**: If Conv maps to GEMM opcodes, lane accounting must stay consistent — add regression tests verifying `lane_usage` counters for Conv-derived commands.
- **Doc/code divergence**: Tie regeneration commands into checklist and note them in `project_board.md` to keep specs aligned.
