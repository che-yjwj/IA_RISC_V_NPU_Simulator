from pathlib import Path

from src.cq import CommandQueue, load_cq_trace, load_isa_spec


def build_valid_queue() -> CommandQueue:
    return CommandQueue.from_iterable(
        [
            {
                "cmd_id": "dma_in",
                "opcode": "DMA_2D",
                "operands": {
                    "src": "dram://input",
                    "dst": "spm://tile0",
                    "shape": [64, 64],
                },
            },
            {
                "cmd_id": "gemm_0",
                "opcode": "TE_GEMM",
                "deps": ["dma_in"],
                "operands": {
                    "m": 64,
                    "n": 64,
                    "k": 64,
                    "a": "spm://tile0",
                    "b": "dram://weights",
                },
            },
            {
                "cmd_id": "vec_add_0",
                "opcode": "VEC_ADD",
                "deps": ["gemm_0"],
                "operands": {
                    "dst": "spm://vec_out0",
                    "src0": "spm://vec_in0",
                    "src1": "spm://vec_in1",
                    "length": 128,
                    "stride": 1,
                },
            },
        ]
    )


def test_load_isa_spec_contains_known_opcodes() -> None:
    spec = load_isa_spec()

    assert spec.get_operation("DMA_2D") is not None
    assert spec.get_operation("TE_GEMM") is not None
    assert spec.get_operation("VEC_ADD") is not None
    assert spec.version >= 1


def test_validate_queue_success() -> None:
    queue = build_valid_queue()
    spec = load_isa_spec()

    issues, covered = spec.validate_queue(queue)

    assert issues == []
    assert {"DMA_2D", "TE_GEMM", "VEC_ADD"}.issubset(covered)


def test_validate_queue_reports_missing_operands() -> None:
    queue = CommandQueue.from_iterable(
        [
            {
                "cmd_id": "dma_missing",
                "opcode": "DMA_2D",
                "operands": {"src": "dram://input"},
            }
        ]
    )
    spec = load_isa_spec()

    issues, _ = spec.validate_queue(queue)

    assert any(issue.kind == "missing_operands" for issue in issues)


def test_validate_queue_reports_unknown_opcode() -> None:
    queue = CommandQueue.from_iterable(
        [
            {
                "cmd_id": "custom",
                "opcode": "CUSTOM_OP",
            }
        ]
    )
    spec = load_isa_spec()

    issues, _ = spec.validate_queue(queue)

    assert any(issue.kind == "unknown_opcode" for issue in issues)


def test_validate_queue_reports_vector_missing_and_unexpected_operands() -> None:
    queue = CommandQueue.from_iterable(
        [
            {
                "cmd_id": "vec_add_bad",
                "opcode": "VEC_ADD",
                "operands": {
                    "dst": "spm://vec_out0",
                    "src0": "spm://vec_in0",
                    # src1 missing on purpose
                    "length": 64,
                    "stride": 1,
                    "unexpected": True,
                },
            }
        ]
    )
    spec = load_isa_spec()

    issues, _ = spec.validate_queue(queue)

    assert len(issues) == 2
    found = {(issue.kind, issue.details.get("operands")) for issue in issues}
    expected = {
        ("missing_operands", ("src1",)),
        ("unexpected_operands", ("unexpected",)),
    }
    assert found == expected


def test_sample_workload_matches_spec() -> None:
    root = Path(__file__).resolve().parents[3]
    trace_path = root / "workloads" / "cq" / "sample_gemm.jsonl"
    spec = load_isa_spec()

    queue = load_cq_trace(trace_path)
    issues, _ = spec.validate_queue(queue)

    assert issues == []
