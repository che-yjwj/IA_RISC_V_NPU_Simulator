from pathlib import Path

from src.simulator.cq_runner import compare_cq_vs_elf


def test_compare_cq_vs_elf_stub(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    cq_path = root / "workloads" / "cq" / "sample_gemm.jsonl"

    result = compare_cq_vs_elf(cq_trace=cq_path)

    assert result["status"] == "cq_ready_elf_pending"
    assert result["cq_trace"] == str(cq_path)
    assert result["cq_summary"]["plan_summary"] == {"dma": 2, "gemm": 1, "fence": 0}
    assert result["elf_summary"]["status"] == "not_provided"

    elf_path = cq_path.with_suffix(".elf")
    placeholder = compare_cq_vs_elf(cq_trace=cq_path, elf_path=elf_path)
    assert placeholder["elf_summary"]["status"] == "error"
    assert placeholder["elf_summary"]["path"] == str(elf_path)
