import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from src.scripts.cq_vs_elf_benchmark import main


def test_cq_vs_elf_cli_json():
    root = Path(__file__).resolve().parents[3]
    cq_path = root / "workloads" / "cq" / "sample_gemm.jsonl"

    buffer = StringIO()
    with redirect_stdout(buffer):
        exit_code = main(["--cq", str(cq_path), "--json"])
    assert exit_code == 0

    payload = json.loads(buffer.getvalue())
    assert payload["cq_summary"]["plan_summary"] == {"dma": 2, "gemm": 1, "fence": 0}
    assert payload["elf_summary"]["status"] == "not_provided"

    elf_path = cq_path.with_suffix(".elf")
    buffer = StringIO()
    with redirect_stdout(buffer):
        main(["--cq", str(cq_path), "--elf", str(elf_path), "--json"])
    payload = json.loads(buffer.getvalue())
    assert payload["elf_summary"]["status"] in {"ok", "error"}
