from src.cq import map_ir_to_isa


def test_vector_add_dependencies_are_inferred_from_operands():
    ir_nodes = [
        {
            "id": "load_a",
            "op": "copy",
            "cmd_id": "dma_load_a",
            "src": "dram://a",
            "dst": "spm://vec_a",
            "shape": [16, 1],
            "strides": [16, 1],
            "trace_id": "vec0",
            "ir_operation": "load_a",
        },
        {
            "id": "load_b",
            "op": "copy",
            "cmd_id": "dma_load_b",
            "src": "dram://b",
            "dst": "spm://vec_b",
            "shape": [16, 1],
            "strides": [16, 1],
            "trace_id": "vec0",
            "ir_operation": "load_b",
        },
        {
            "id": "vec_add",
            "op": "vector_add",
            "cmd_id": "vec_add0",
            "src0": "spm://vec_a",
            "src1": "spm://vec_b",
            "dst": "spm://vec_out",
            "length": 16,
            "stride": 1,
            "trace_id": "vec0",
            "ir_operation": "vector_add",
        },
        {
            "id": "store",
            "op": "copy",
            "cmd_id": "dma_store",
            "src": "spm://vec_out",
            "dst": "dram://out",
            "shape": [16, 1],
            "strides": [16, 1],
            "trace_id": "vec0",
            "ir_operation": "store",
        },
    ]

    instructions = map_ir_to_isa(ir_nodes)

    assert instructions[2]["opcode"] == "VEC_ADD"
    assert set(instructions[2]["deps"]) == {"dma_load_a", "dma_load_b"}
    assert instructions[3]["deps"] == ["vec_add0"]
