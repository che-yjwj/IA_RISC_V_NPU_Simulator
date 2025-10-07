from src.cq import map_ir_to_isa


def _load_sample_ir():
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


def test_map_ir_to_isa_generates_expected_sequence():
    ir_graph = _load_sample_ir()
    instructions = map_ir_to_isa(ir_graph)

    assert [instr["cmd_id"] for instr in instructions] == [
        "dma_in",
        "gemm_0",
        "dma_out",
    ]
    assert instructions[1]["opcode"] == "TE_GEMM"
    assert instructions[1]["deps"] == ["dma_in"]
    assert instructions[1]["trace"]["ir_id"] == "matmul_tile0"
    assert instructions[1]["trace"]["isa_idx"] == 1
    assert instructions[1]["operands"]["a"] == "spm://tile0"
    assert instructions[2]["deps"] == ["gemm_0"]
