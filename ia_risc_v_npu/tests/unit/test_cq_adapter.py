from src.cq import (
    CommandQueue,
    CQCommand,
    build_execution_plan,
    load_isa_spec,
)


def make_queue() -> CommandQueue:
    commands = [
        {
            "cmd_id": "dma_in",
            "opcode": "DMA_2D",
            "operands": {
                "src": "dram://input",
                "dst": "spm://tile0",
                "shape": [64, 64],
                "strides": [64, 1],
            },
        },
        {
            "cmd_id": "gemm_0",
            "opcode": "TE_GEMM",
            "deps": ["dma_in"],
            "operands": {
                "m": 64,
                "n": 64,
                "k": 32,
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
                "stride": 2,
            },
        },
        {
            "cmd_id": "sync",
            "opcode": "FENCE_SPM",
            "deps": ["gemm_0"],
            "operands": {},
        },
    ]
    return CommandQueue.from_iterable(commands)


def test_build_execution_plan() -> None:
    queue = make_queue()
    spec = load_isa_spec()

    plan = build_execution_plan(queue, spec)

    assert plan.summary() == {"dma": 1, "gemm": 1, "vector": 1, "fence": 1}
    dma = plan.dma_ops[0]
    assert dma.src == "dram://input"
    assert dma.shape == (64, 64)
    assert dma.strides == (64, 1)

    gemm = plan.gemm_ops[0]
    assert gemm.m == 64
    assert gemm.n == 64
    assert gemm.k == 32
    assert gemm.c is None

    vector = plan.vector_ops[0]
    assert vector.dst == "spm://vec_out0"
    assert vector.length == 128
    assert vector.stride == 2

    fence = plan.fence_ops[0]
    assert fence.target is None


def test_missing_operand_raises() -> None:
    bad_command = CQCommand.from_dict(
        {
            "cmd_id": "gemm_bad",
            "opcode": "TE_GEMM",
            "operands": {"m": 16, "n": 16, "a": "spm://a", "b": "spm://b"},
        }
    )
    queue = CommandQueue.from_iterable([bad_command.to_dict()])
    spec = load_isa_spec()

    try:
        build_execution_plan(queue, spec)
    except Exception as exc:  # noqa: BLE001 - simple guard for ISASpecError
        assert "operand 'k' must be present" in str(exc)
    else:  # pragma: no cover - fail fast if exception not raised
        raise AssertionError("Expected build_execution_plan to raise")
