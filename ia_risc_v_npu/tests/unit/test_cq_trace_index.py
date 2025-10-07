from pathlib import Path

from src.cq import build_trace_index, load_cq_trace


def test_build_trace_index_groups_commands_by_ir():
    root = Path(__file__).resolve().parents[3]
    trace_path = root / "workloads" / "cq" / "sample_gemm.jsonl"

    queue = load_cq_trace(trace_path)
    index = build_trace_index(queue)

    # Validate lookup by command id.
    gemm_link = index.for_command("gemm_0")
    assert gemm_link is not None
    assert gemm_link.isa_idx == 1
    assert gemm_link.ir_id == "matmul_tile0"

    # All commands should map back to the same IR id in isa order.
    chain = index.for_ir("matmul_tile0")
    assert [link.cmd_id for link in chain] == ["dma_in", "gemm_0", "dma_out"]
    assert [link.isa_idx for link in chain] == [0, 1, 2]
    assert len(index) == len(queue)
