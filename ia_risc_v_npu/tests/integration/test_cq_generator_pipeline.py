from pathlib import Path

from src.cq import generate_command_queue, load_cq_trace


def _sample_ir_graph():
    return [
        {
            "id": "load_inputs",
            "op": "copy",
            "cmd_id": "dma_in",
            "src": "dram://inputs",
            "dst": "spm://tile0",
            "shape": [64, 64],
            "strides": [64, 1],
            "trace_id": "matmul_tile0",
            "ir_operation": "load",
        },
        {
            "id": "matmul_tile0",
            "op": "conv2d",
            "depends_on": ["dma_in"],
            "commands": {
                "compute": "gemm_0",
                "store": "dma_out",
            },
            "tile": {"m": 64, "n": 64, "k": 64},
            "operands": {
                "activation": "spm://tile0",
                "weights": "dram://weights",
                "output": "spm://tile0",
            },
            "output": "dram://outputs",
            "output_shape": [64, 64],
            "output_strides": [64, 1],
            "trace_id": "matmul_tile0",
            "ir_operation": "matmul",
            "store_operation": "store",
        },
    ]


def test_generate_command_queue_matches_sample_trace():
    root = Path(__file__).resolve().parents[3]
    sample_trace = load_cq_trace(root / "workloads" / "cq" / "sample_gemm.jsonl")

    generated = generate_command_queue(
        _sample_ir_graph(), metadata=sample_trace.metadata
    )

    assert generated.command_ids() == sample_trace.command_ids()
    assert [cmd.opcode for cmd in generated.commands] == [
        cmd.opcode for cmd in sample_trace.commands
    ]

    for generated_cmd, sample_cmd in zip(generated.commands, sample_trace.commands):
        assert generated_cmd.operands == sample_cmd.operands
        assert generated_cmd.dependencies == sample_cmd.dependencies
        assert generated_cmd.trace["ir_id"] == sample_cmd.trace["ir_id"]
        assert generated_cmd.trace["isa_idx"] == sample_cmd.trace["isa_idx"]
