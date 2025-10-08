import pytest

from src.cq.mapper import RuleError, load_rules, map_ir_to_isa


def test_conv_rule_emits_gemm_and_store():
    rules = load_rules(None)
    ir_node = {
        "op": "conv2d",
        "trace_id": "conv_tile0",
        "ir_operation": "te_conv2d",
        "store_operation": "store_tile",
        "commands": {
            "compute": "conv_tile0_gemm",
            "store": "conv_tile0_store",
        },
        "depends_on": ["dma_inputs", "dma_weights"],
        "tile": {"m": 16, "n": 8, "k": 16},
        "operands": {
            "activation": "spm://conv_input_tile",
            "weights": "spm://conv_weight_tile",
            "output": "spm://conv_output_tile",
        },
        "output": "dram://conv_outputs",
        "output_shape": [16, 8],
        "output_strides": [8, 1],
        "trace": {"source_opcode": "TE_CONV2D"},
    }

    commands = map_ir_to_isa([ir_node], rules=rules)
    assert len(commands) == 2

    gemm_cmd = commands[0]
    assert gemm_cmd["cmd_id"] == "conv_tile0_gemm"
    assert gemm_cmd["opcode"] == "TE_GEMM"
    assert gemm_cmd["operands"]["m"] == 16
    assert gemm_cmd["operands"]["n"] == 8
    assert gemm_cmd["operands"]["k"] == 16
    assert gemm_cmd["trace"]["ir_id"] == "conv_tile0"

    store_cmd = commands[1]
    assert store_cmd["cmd_id"] == "conv_tile0_store"
    assert store_cmd["opcode"] == "DMA_2D"
    assert store_cmd["deps"] == ["conv_tile0_gemm"]
    assert store_cmd["operands"]["dst"] == "dram://conv_outputs"


def test_conv_rule_missing_tile_values_raises():
    rules = load_rules(None)
    ir_node = {
        "op": "conv2d",
        "trace_id": "bad_conv",
        "commands": {"compute": "bad_conv_gemm", "store": "bad_conv_store"},
        "operands": {
            "activation": "spm://missing_tile",
            "weights": "spm://missing_weights",
        },
        "output": "dram://conv_outputs",
        "output_shape": [1, 1],
        "output_strides": [1, 1],
    }

    with pytest.raises(RuleError):
        map_ir_to_isa([ir_node], rules=rules)
