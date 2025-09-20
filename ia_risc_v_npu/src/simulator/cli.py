"""Command-line interface for the IA RISC-V + NPU simulator."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterable, List, Optional

try:  # pragma: no cover - import guarded for environments without pyelftools
    from elftools.elf.elffile import ELFFile
except ImportError:  # pragma: no cover - fallback handled at runtime
    ELFFile = None  # type: ignore[assignment]

from src.simulator.main import AdaptiveSimulator, SimulationReport, DRAM_SIZE

LOGGER = logging.getLogger(__name__)


class CLIError(RuntimeError):
    """Raised when the CLI cannot complete the requested action."""


@dataclass(slots=True)
class ProgramImage:
    instructions: List[int]
    text_size: int


@dataclass(slots=True)
class BenchmarkMetrics:
    elapsed_seconds: float
    instructions_executed: int
    mips: float


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


def load_config(config_path: Optional[Path]) -> dict:
    if not config_path:
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise CLIError(f"Config file not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise CLIError(f"Config file is not valid JSON: {config_path}") from exc

    if not isinstance(data, dict):
        raise CLIError("Config file must contain a JSON object")
    return data


def _extract_instruction_words(data: bytes) -> List[int]:
    if len(data) % 4 != 0:
        raise CLIError("Executable section size must be word-aligned (4 bytes)")
    words = [int.from_bytes(data[i : i + 4], "little", signed=False) for i in range(0, len(data), 4)]
    return words


def load_program_image(elf_path: Path) -> ProgramImage:
    if ELFFile is None:
        raise CLIError("pyelftools is required to load ELF binaries. Install it via 'pip install pyelftools'.")
    try:
        with elf_path.open("rb") as handle:
            elf = ELFFile(handle)
            exec_sections: List[tuple[int, bytes]] = []

            text_section = elf.get_section_by_name(".text")
            if text_section and text_section.data():
                exec_sections.append((text_section["sh_addr"], text_section.data()))

            if not exec_sections:
                for section in elf.iter_sections():
                    flags = int(section["sh_flags"])
                    data = section.data()
                    if flags & 0x4 and data:  # SHF_EXECINSTR
                        exec_sections.append((section["sh_addr"], data))

    except FileNotFoundError as exc:
        raise CLIError(f"ELF file not found: {elf_path}") from exc
    except OSError as exc:
        raise CLIError(f"Failed to read ELF file: {elf_path}") from exc

    if not exec_sections:
        raise CLIError("ELF file does not contain executable instructions")

    exec_sections.sort(key=lambda item: item[0])
    instructions: List[int] = []
    for _, data in exec_sections:
        instructions.extend(_extract_instruction_words(data))

    text_size = sum(len(data) for _, data in exec_sections)
    return ProgramImage(instructions=instructions, text_size=text_size)


def write_output(
    result: SimulationReport,
    output_path: Optional[Path],
    instruction_count: int,
    *,
    extra: Optional[dict] = None,
) -> None:
    summary = {
        "cycles": result.cycles,
        "halted": result.halted,
        "reason": result.reason,
        "sim_time": result.sim_time,
        "instructions_executed": instruction_count,
    }
    if extra:
        summary.update(extra)
    LOGGER.info(
        "Simulation finished: cycles=%s halted=%s reason=%s", result.cycles, result.halted, result.reason
    )
    if output_path:
        try:
            with output_path.open("w", encoding="utf-8") as handle:
                json.dump(summary, handle, indent=2)
        except OSError as exc:
            raise CLIError(f"Failed to write output file: {output_path}") from exc


def run_simulate(args: argparse.Namespace) -> int:
    configure_logging(args.verbose)
    config = load_config(args.config)
    max_cycles = int(config.get("max_cycles", 0) or 0)

    program = load_program_image(args.elf_file)
    simulator = AdaptiveSimulator()
    simulator.load_program(program.instructions)

    LOGGER.debug("Loaded %s bytes (%s instructions)", program.text_size, len(program.instructions))

    result = asyncio.run(simulator.run_simulation(max_cycles=max_cycles))
    write_output(result, args.output, simulator.risc_v_engine.instruction_count)
    return 0


def _generate_synthetic_program(length: int) -> ProgramImage:
    if length <= 0:
        raise CLIError("Synthetic program length must be positive")

    # DRAM holds 1MB, so ensure the program fits.
    max_words = (DRAM_SIZE // 4) - 1  # reserve space for halt instruction
    if length > max_words:
        raise CLIError(f"Synthetic program length exceeds DRAM capacity ({max_words} instructions)")

    add_instruction = 0x003100B3  # ADD x1, x2, x3
    program = [add_instruction] * length
    program.append(0)  # halt sentinel
    return ProgramImage(instructions=program, text_size=len(program) * 4)


def _measure_performance(simulator: AdaptiveSimulator, max_cycles: int) -> tuple[SimulationReport, BenchmarkMetrics]:
    start = perf_counter()
    result = asyncio.run(simulator.run_simulation(max_cycles=max_cycles))
    elapsed = perf_counter() - start
    executed = simulator.risc_v_engine.instruction_count
    mips = (executed / elapsed / 1_000_000) if elapsed > 0 else 0.0
    metrics = BenchmarkMetrics(elapsed_seconds=elapsed, instructions_executed=executed, mips=mips)
    return result, metrics


def run_benchmark(args: argparse.Namespace) -> int:
    configure_logging(args.verbose)
    config = load_config(args.config)
    max_cycles = int(config.get("max_cycles", 0) or args.max_cycles or 0)

    if args.elf_file:
        program = load_program_image(args.elf_file)
    else:
        program = _generate_synthetic_program(args.instructions)

    simulator = AdaptiveSimulator()
    simulator.load_program(program.instructions)

    LOGGER.debug(
        "Benchmark program loaded: %s instructions (%s bytes)",
        len(program.instructions),
        program.text_size,
    )

    result, metrics = _measure_performance(simulator, max_cycles)

    LOGGER.info(
        "Benchmark completed: elapsed=%.4fs, instructions=%s, MIPS=%.2f",
        metrics.elapsed_seconds,
        metrics.instructions_executed,
        metrics.mips,
    )

    write_output(
        result,
        args.output,
        simulator.risc_v_engine.instruction_count,
        extra={
            "elapsed_seconds": metrics.elapsed_seconds,
            "mips": metrics.mips,
        },
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IA RISC-V + NPU Simulator CLI")
    subparsers = parser.add_subparsers(dest="command")

    simulate_parser = subparsers.add_parser("simulate", help="run a simulation from an ELF binary")
    simulate_parser.add_argument("elf_file", type=Path, help="Path to the RISC-V ELF binary")
    simulate_parser.add_argument(
        "--config", type=Path, default=None, help="Path to a JSON config file with simulation options"
    )
    simulate_parser.add_argument(
        "--output", type=Path, default=None, help="Write simulation summary to the specified path"
    )
    simulate_parser.add_argument("--verbose", action="store_true", help="Enable verbose logging output")
    simulate_parser.set_defaults(handler=run_simulate)

    benchmark_parser = subparsers.add_parser(
        "benchmark", help="measure wall-clock performance and report MIPS"
    )
    benchmark_parser.add_argument(
        "--elf-file",
        type=Path,
        default=None,
        help="Optional path to a RISC-V ELF binary to benchmark",
    )
    benchmark_parser.add_argument(
        "--instructions",
        type=int,
        default=200_000,
        help="Synthetic ADD instruction count when no ELF is provided",
    )
    benchmark_parser.add_argument(
        "--max-cycles",
        type=int,
        default=0,
        help="Optional cycle cap for the benchmark run",
    )
    benchmark_parser.add_argument(
        "--config", type=Path, default=None, help="Path to a JSON config file with simulation options"
    )
    benchmark_parser.add_argument(
        "--output", type=Path, default=None, help="Write benchmark summary to the specified path"
    )
    benchmark_parser.add_argument("--verbose", action="store_true", help="Enable verbose logging output")
    benchmark_parser.set_defaults(handler=run_benchmark)

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not hasattr(args, "handler"):
        parser.print_help()
        return 1

    try:
        return args.handler(args)
    except CLIError as exc:
        LOGGER.error("%s", exc)
        return 1


__all__ = [
    "main",
    "load_program_image",
    "load_config",
    "CLIError",
    "BenchmarkMetrics",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
