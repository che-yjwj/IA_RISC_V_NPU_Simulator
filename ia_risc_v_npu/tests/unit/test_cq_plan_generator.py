import json
from argparse import Namespace
from pathlib import Path

import pytest

from src.cq.io import load_cq_trace
from src.cq.tools.plan_generator import PlanError, run


def _write_plan(tmp_path: Path) -> Path:
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        """
metadata:
  name: sample
  description: demo
commands:
  - cmd_id: dma_in
    opcode: DMA_2D
    operands:
      src: dram://inputs
      dst: spm://tile0
      shape: [4, 4]
      strides: [4, 1]
    trace:
      ir_operation: load
  - cmd_id: gemm
    opcode: TE_GEMM
    deps: [dma_in]
    operands:
      m: 4
      n: 4
      k: 4
      a: spm://tile0
      b: dram://weights
    trace:
      ir_operation: compute
  - cmd_id: dma_out
    opcode: DMA_2D
    deps: [gemm]
    operands:
      src: spm://tile0
      dst: dram://outputs
      shape: [4, 4]
      strides: [4, 1]
    trace:
      ir_operation: store
""".strip(),
        encoding="utf-8",
    )
    return plan


def test_plan_generator_writes_jsonl(tmp_path: Path):
    plan_path = _write_plan(tmp_path)
    output_path = tmp_path / "trace.jsonl"

    args = Namespace(
        input=plan_path,
        output=output_path,
        isa=None,
        allow_forward_deps=False,
        indent=None,
    )

    exit_code = run(args)
    assert exit_code == 0

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert lines
    first = json.loads(lines[0])
    assert first["metadata"]["name"] == "sample"

    queue = load_cq_trace(output_path)
    assert queue.command_ids() == ("dma_in", "gemm", "dma_out")


def test_plan_generator_validates_isa(tmp_path: Path):
    plan_path = _write_plan(tmp_path)
    output_path = tmp_path / "trace.jsonl"
    root = Path(__file__).resolve().parents[3]

    args = Namespace(
        input=plan_path,
        output=output_path,
        isa=root / "specs" / "isa.yaml",
        allow_forward_deps=False,
        indent=None,
    )

    exit_code = run(args)
    assert exit_code == 0

    # Corrupt the opcode to trigger validation failure.
    bad_plan = tmp_path / "bad.yaml"
    bad_plan.write_text(
        """
metadata: {name: bad}
commands:
  - cmd_id: bad
    opcode: UNKNOWN
""".strip(),
        encoding="utf-8",
    )

    bad_args = Namespace(
        input=bad_plan,
        output=output_path,
        isa=root / "specs" / "isa.yaml",
        allow_forward_deps=False,
        indent=None,
    )

    with pytest.raises(PlanError):
        run(bad_args)
