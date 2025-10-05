"""Command-line interface for the IA RISC-V + NPU simulator."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterable, List, Optional

try:  # pragma: no cover - import guarded for environments without pyelftools
    from elftools.elf.elffile import ELFFile
except ImportError:  # pragma: no cover - fallback handled at runtime
    ELFFile = None  # type: ignore[assignment]

try:  # pragma: no cover - mirrors ELFFile guard
    from elftools.elf.constants import SH_FLAGS  # type: ignore[no-redef]
except ImportError:  # pragma: no cover - pyelftools optional at runtime
    SH_FLAGS = None  # type: ignore[assignment]

from src.cq.io import CQIOError, load_cq_trace
from src.cq.schema import CommandQueue
from src.cq.spec import ISASpecError, load_isa_spec
from src.simulator.accuracy import AccuracyGuardError, evaluate_accuracy_guard
from src.simulator.config import (
    ConfigValidationError,
    default_simulator_config,
    validate_simulator_config,
)
from src.simulator.identifiers import DRAM as DRAM_REGION
from src.simulator.main import AdaptiveSimulator, SimulationReport
from src.simulator.program import ProgramImage, ProgramSegment

LOGGER = logging.getLogger(__name__)
TRACE_COMPONENT_CHOICES: tuple[str, ...] = ("bus", "memory", "npu")


class CLIError(RuntimeError):
    """Raised when the CLI cannot complete the requested action."""


@dataclass(slots=True)
class BenchmarkMetrics:
    elapsed_seconds: float
    instructions_executed: int
    mips: float


def configure_logging(
    config: dict,
    verbose: bool,
    *,
    log_level: str | None = None,
    log_path: Path | None = None,
    trace_components: Iterable[str] | None = None,
) -> logging.Logger:
    """Configure root logging and return the simulator logger."""

    logging_config = config.get("logging", {})

    # CLI arguments override config file settings
    level_name = (log_level or logging_config.get("level", "INFO")).upper()
    if verbose:
        level_name = "DEBUG"

    path = log_path or logging_config.get("path")
    traces = set(trace_components or logging_config.get("trace_components", []))

    level = getattr(logging, level_name, logging.INFO)

    # Reset any existing logging configuration
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers[:]:
            root.removeHandler(handler)

    # Set up the new handler
    handler: logging.Handler
    if path:
        handler = logging.FileHandler(path, mode="w")
    else:
        handler = logging.StreamHandler()

    formatter = logging.Formatter("%(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)  # Set root to lowest level to not filter children

    simulator_logger = logging.getLogger("simulator")
    # Set parent logger to DEBUG so that traced children are not filtered.
    simulator_logger.setLevel(logging.DEBUG)

    for component in TRACE_COMPONENT_CHOICES:
        component_logger = simulator_logger.getChild(component)
        if component in traces:
            component_logger.setLevel(logging.DEBUG)
        else:
            component_logger.setLevel(level)

    # Ensure CLI messages follow the configured verbosity.
    LOGGER.setLevel(level)

    return simulator_logger


def load_config(config_path: Optional[Path]) -> dict:
    if not config_path:
        return default_simulator_config()
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise CLIError(f"Config file not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise CLIError(f"Config file is not valid JSON: {config_path}") from exc

    if not isinstance(data, dict):
        raise CLIError("Config file must contain a JSON object")

    try:
        return validate_simulator_config(data)
    except ConfigValidationError as exc:
        raise CLIError(f"Invalid configuration: {exc}") from exc


def _extract_instruction_words(data: bytes) -> List[int]:
    if len(data) % 4 != 0:
        raise CLIError("Executable section size must be word-aligned (4 bytes)")
    words = [
        int.from_bytes(data[i : i + 4], "little", signed=False)
        for i in range(0, len(data), 4)
    ]
    return words


def load_program_image(elf_path: Path) -> ProgramImage:
    if ELFFile is None:
        raise CLIError(
            (
                "pyelftools is required to load ELF binaries. "
                "Install it via 'pip install pyelftools'."
            )
        )
    try:
        with elf_path.open("rb") as handle:
            elf = ELFFile(handle)
            exec_sections: List[tuple[int, bytes]] = []
            load_segments: List[ProgramSegment] = []
            exec_flag = (
                getattr(SH_FLAGS, "SHF_EXECINSTR", 0x4) if SH_FLAGS is not None else 0x4
            )

            text_section = elf.get_section_by_name(".text")
            if text_section and text_section.data():
                exec_sections.append((text_section["sh_addr"], text_section.data()))

            if not exec_sections:
                for section in elf.iter_sections():
                    flags = int(section["sh_flags"])
                    data = section.data()
                    if flags & exec_flag and data:
                        exec_sections.append((section["sh_addr"], data))

            for segment in elf.iter_segments():
                if segment["p_type"] != "PT_LOAD":
                    continue

                raw_data = segment.data() or b""
                mem_size = int(segment["p_memsz"])
                if mem_size < len(raw_data):
                    raise CLIError(
                        "ELF load segment has memsz smaller than file payload"
                    )

                address = int(segment["p_paddr"] or segment["p_vaddr"])
                load_segments.append(
                    ProgramSegment(address=address, data=raw_data, mem_size=mem_size)
                )

    except FileNotFoundError as exc:
        raise CLIError(f"ELF file not found: {elf_path}") from exc
    except OSError as exc:
        raise CLIError(f"Failed to read ELF file: {elf_path}") from exc

    if not exec_sections:
        raise CLIError("ELF file does not contain executable instructions")
    if not load_segments:
        raise CLIError("ELF file does not contain loadable segments")

    exec_sections.sort(key=lambda item: item[0])
    instructions: List[int] = []
    for _, data in exec_sections:
        instructions.extend(_extract_instruction_words(data))

    text_size = sum(len(data) for _, data in exec_sections)
    entry_point = int(elf.header["e_entry"])
    return ProgramImage(
        instructions=instructions,
        text_size=text_size,
        entry_point=entry_point,
        segments=load_segments,
    )


def prepare_summary(
    result: SimulationReport,
    instruction_count: int,
    *,
    extra: Optional[dict] = None,
) -> dict:
    summary = {
        "cycles": result.cycles,
        "halted": result.halted,
        "reason": result.reason,
        "sim_time": result.sim_time,
        "instructions_executed": instruction_count,
        "elapsed_seconds": result.elapsed_seconds,
        "mips": result.mips,
        "memory_report": result.memory_report,
        "stall_breakdown": result.stall_breakdown,
        "npu_metrics": result.npu_metrics,
        "fetch_metrics": result.fetch_metrics,
    }
    cache_metrics = result.memory_report.get("caches", {})
    miss_rates = {
        name.lower(): metrics.get("miss_rate", 0.0)
        for name, metrics in cache_metrics.items()
    }
    if result.fetch_metrics:
        miss_rates["icache"] = result.fetch_metrics.get("miss_rate", 0.0)
    summary["miss_rates"] = miss_rates

    memory_system_metrics = result.memory_report.get("memory_system", {})
    summary["amat_cycles"] = memory_system_metrics.get("average_latency_cycles", 0.0)
    summary["npu_util"] = result.npu_metrics.get("utilization", 0.0)
    if extra:
        summary.update(extra)
    return summary


def write_output(summary: dict, output_path: Optional[Path]) -> None:
    LOGGER.info(
        "Simulation finished: cycles=%s halted=%s reason=%s",
        summary.get("cycles"),
        summary.get("halted"),
        summary.get("reason"),
    )
    if output_path:
        try:
            with output_path.open("w", encoding="utf-8") as handle:
                json.dump(summary, handle, indent=2)
        except OSError as exc:
            raise CLIError(f"Failed to write output file: {output_path}") from exc


def _setup_environment(args: argparse.Namespace) -> tuple[dict, logging.Logger]:
    """Load config, override with CLI args, and configure logging."""
    config = load_config(args.config)

    # Override config with CLI arguments where provided.
    if getattr(args, "scheduler_policy", None):
        config["npu"]["policy"] = args.scheduler_policy

    simulator_logger = configure_logging(
        config,
        args.verbose,
        log_level=getattr(args, "log_level", None),
        log_path=getattr(args, "log_path", None),
        trace_components=getattr(args, "trace", None),
    )
    return config, simulator_logger


def run_simulate(args: argparse.Namespace) -> int:
    config, simulator_logger = _setup_environment(args)
    max_cycles = int(config.get("max_cycles", 0) or 0)

    program = load_program_image(args.elf_file)
    simulator = AdaptiveSimulator(config=config, logger=simulator_logger)
    simulator.load_program(program)

    LOGGER.debug(
        "Loaded %s bytes (%s instructions)",
        program.text_size,
        len(program.instructions),
    )

    result = asyncio.run(simulator.run_simulation(max_cycles=max_cycles))
    summary = prepare_summary(result, simulator.risc_v_engine.instruction_count)

    guard_config = config.get("accuracy_guard", {})
    base_path = args.config.parent if args.config else Path.cwd()
    try:
        guard_outcome = evaluate_accuracy_guard(
            summary, guard_config, base_path=base_path
        )
    except AccuracyGuardError as exc:
        raise CLIError(str(exc)) from exc

    exit_code = 0
    if guard_outcome is not None:
        summary["accuracy_guard"] = guard_outcome.payload
        exit_code = 0 if guard_outcome.passed else 1

    write_output(summary, args.output)
    return exit_code


def _generate_synthetic_program(length: int) -> ProgramImage:
    if length <= 0:
        raise CLIError("Synthetic program length must be positive")

    # DRAM holds 1MB, so ensure the program fits.
    max_words = (DRAM_REGION.size // 4) - 1  # reserve space for halt instruction
    if length > max_words:
        raise CLIError(
            f"Synthetic program length exceeds DRAM capacity ({max_words} instructions)"
        )

    add_instruction = 0x003100B3  # ADD x1, x2, x3
    program = [add_instruction] * length
    program.append(0)  # halt sentinel
    program_bytes = b"".join(
        int(word).to_bytes(4, "little", signed=False) for word in program
    )
    segment = ProgramSegment(
        address=DRAM_REGION.base,
        data=program_bytes,
        mem_size=len(program_bytes),
    )
    return ProgramImage(
        instructions=program,
        text_size=len(program) * 4,
        entry_point=segment.address,
        segments=[segment],
    )


def _measure_performance(
    simulator: AdaptiveSimulator, max_cycles: int
) -> tuple[SimulationReport, BenchmarkMetrics]:
    start = perf_counter()
    result = asyncio.run(simulator.run_simulation(max_cycles=max_cycles))
    elapsed = perf_counter() - start
    executed = simulator.risc_v_engine.instruction_count
    mips = (executed / elapsed / 1_000_000) if elapsed > 0 else 0.0
    metrics = BenchmarkMetrics(
        elapsed_seconds=elapsed, instructions_executed=executed, mips=mips
    )
    return result, metrics


def _evaluate_mips_guard(
    metrics: BenchmarkMetrics,
    *,
    min_mips: float | None,
    max_mips: float | None,
) -> dict[str, float | bool | None] | None:
    if min_mips is None and max_mips is None:
        return None

    measured = metrics.mips
    passed = True
    if min_mips is not None and measured < min_mips:
        passed = False
    if max_mips is not None and measured > max_mips:
        passed = False

    return {
        "min_mips": min_mips,
        "max_mips": max_mips,
        "measured_mips": measured,
        "passed": passed,
    }


def run_benchmark(args: argparse.Namespace) -> int:
    config, simulator_logger = _setup_environment(args)
    max_cycles = int(config.get("max_cycles", 0) or args.max_cycles or 0)

    if args.elf_file:
        program = load_program_image(args.elf_file)
    else:
        program = _generate_synthetic_program(args.instructions)

    simulator = AdaptiveSimulator(config=config, logger=simulator_logger)
    simulator.load_program(program)

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

    summary = prepare_summary(
        result,
        simulator.risc_v_engine.instruction_count,
        extra={
            "elapsed_seconds": metrics.elapsed_seconds,
            "mips": metrics.mips,
        },
    )

    guard_config = config.get("accuracy_guard", {})
    base_path = args.config.parent if args.config else Path.cwd()
    try:
        guard_outcome = evaluate_accuracy_guard(
            summary, guard_config, base_path=base_path
        )
    except AccuracyGuardError as exc:
        raise CLIError(str(exc)) from exc

    exit_code = 0
    if guard_outcome is not None:
        summary["accuracy_guard"] = guard_outcome.payload
        exit_code = 0 if guard_outcome.passed else 1

    min_mips = getattr(args, "min_mips", None)
    max_mips = getattr(args, "max_mips", None)
    mips_guard = _evaluate_mips_guard(
        metrics,
        min_mips=min_mips,
        max_mips=max_mips,
    )
    if mips_guard is not None:
        summary["mips_guard"] = mips_guard
        if not mips_guard["passed"]:
            LOGGER.error(
                "Measured MIPS %.2f outside guard range (min=%s, max=%s)",
                metrics.mips,
                args.min_mips,
                args.max_mips,
            )
            exit_code = 1

    write_output(summary, args.output)
    return exit_code


def _summarise_command_queue(
    queue: CommandQueue,
    *,
    isa_summary: Optional[dict] = None,
) -> dict:
    histogram = Counter(command.opcode for command in queue)
    dependency_lengths = [len(command.dependencies) for command in queue]
    total_dependencies = sum(dependency_lengths)
    dependency_stats = {
        "total": total_dependencies,
        "max": max(dependency_lengths) if dependency_lengths else 0,
        "roots": sum(1 for length in dependency_lengths if length == 0),
    }
    summary: dict = {
        "command_count": len(queue),
        "unique_opcodes": len(histogram),
        "opcode_histogram": dict(sorted(histogram.items())),
        "dependency_stats": dependency_stats,
        "command_id_preview": list(queue.command_ids()[:5]),
        "status": "validated",
        "notes": (
            "CQ execution path is experimental; simulator integration will "
            "arrive in later Stage 4 milestones."
        ),
    }
    if queue.metadata:
        summary["metadata"] = dict(queue.metadata)
    if isa_summary:
        summary["isa_validation"] = isa_summary
    return summary


def run_cq(args: argparse.Namespace) -> int:
    _setup_environment(args)
    try:
        queue = load_cq_trace(args.trace, strict=not args.allow_forward_deps)
    except CQIOError as exc:
        raise CLIError(str(exc)) from exc

    isa_summary: Optional[dict] = None
    if not getattr(args, "skip_isa_check", False):
        try:
            isa_spec = load_isa_spec(getattr(args, "isa_spec", None))
        except ISASpecError as exc:
            raise CLIError(str(exc)) from exc

        issues, covered = isa_spec.validate_queue(queue)
        if issues:
            for issue in issues:
                LOGGER.warning(
                    "ISA spec issue for %s (%s): %s",
                    issue.command_id,
                    issue.opcode,
                    issue.kind,
                )
        isa_summary = {
            "status": "passed" if not issues else "failed",
            "spec_version": isa_spec.version,
            "covered_opcodes": sorted(covered),
        }
        if issues:
            isa_summary["issues"] = [issue.to_dict() for issue in issues]
            unknown = sorted(
                {issue.opcode for issue in issues if issue.kind == "unknown_opcode"}
            )
            if unknown:
                isa_summary["unknown_opcodes"] = unknown
        else:
            isa_summary["message"] = "All commands match ISA specification."

    summary = _summarise_command_queue(queue, isa_summary=isa_summary)
    LOGGER.info(
        "Loaded CQ trace '%s' (%s commands, %s unique opcodes)",
        args.trace,
        summary["command_count"],
        summary["unique_opcodes"],
    )

    if args.output:
        try:
            with args.output.open("w", encoding="utf-8") as handle:
                json.dump(summary, handle, indent=2)
        except OSError as exc:  # pragma: no cover - filesystem failure
            raise CLIError(f"Failed to write CQ summary: {args.output}") from exc
    else:
        LOGGER.info(
            "Opcode histogram: %s",
            ", ".join(
                f"{opcode}={count}"
                for opcode, count in summary["opcode_histogram"].items()
            ),
        )

    return 0


def _add_logging_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--log-level",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        default=None,
        help="Set the base logging level (default: INFO; --verbose overrides to DEBUG)",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=None,
        help="Redirect logging to the specified file.",
    )
    parser.add_argument(
        "--trace",
        choices=list(TRACE_COMPONENT_CHOICES),
        action="append",
        default=[],
        help=(
            "Enable detailed DEBUG traces for a specific simulator component "
            "(repeatable)"
        ),
    )


def _add_simulator_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--scheduler-policy",
        choices=["min_finish_time", "rr", "priority"],
        default=None,
        help="Override the NPU scheduler policy from the config file.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IA RISC-V + NPU Simulator CLI")
    subparsers = parser.add_subparsers(dest="command")

    simulate_parser = subparsers.add_parser(
        "simulate", help="run a simulation from an ELF binary"
    )
    simulate_parser.add_argument(
        "elf_file", type=Path, help="Path to the RISC-V ELF binary"
    )
    simulate_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to a JSON config file with simulation options",
    )
    simulate_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write simulation summary to the specified path",
    )
    simulate_parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose logging output"
    )
    _add_logging_arguments(simulate_parser)
    _add_simulator_arguments(simulate_parser)
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
        "--min-mips",
        type=float,
        default=None,
        help="Fail the benchmark if measured MIPS falls below this threshold",
    )
    benchmark_parser.add_argument(
        "--max-mips",
        type=float,
        default=None,
        help="Fail the benchmark if measured MIPS exceeds this threshold",
    )
    benchmark_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to a JSON config file with simulation options",
    )
    benchmark_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write benchmark summary to the specified path",
    )
    benchmark_parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose logging output"
    )
    _add_logging_arguments(benchmark_parser)
    _add_simulator_arguments(benchmark_parser)
    benchmark_parser.set_defaults(handler=run_benchmark)

    cq_parser = subparsers.add_parser(
        "run-cq",
        help=("validate a CQ JSONL trace and inspect its structure (experimental)"),
    )
    cq_parser.add_argument(
        "trace",
        type=Path,
        help="Path to the CQ JSONL trace",
    )
    cq_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional simulator config for logging setup",
    )
    cq_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write the CQ validation summary to the specified file",
    )
    cq_parser.add_argument(
        "--allow-forward-deps",
        action="store_true",
        help="Allow dependencies on commands that appear later in the trace",
    )
    cq_parser.add_argument(
        "--isa-spec",
        type=Path,
        default=None,
        help="Override the default specs/isa.yaml path",
    )
    cq_parser.add_argument(
        "--skip-isa-check",
        action="store_true",
        help="Skip ISA opcode/operand validation",
    )
    cq_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging output",
    )
    _add_logging_arguments(cq_parser)
    cq_parser.set_defaults(handler=run_cq)

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
    "configure_logging",
    "CLIError",
    "BenchmarkMetrics",
    "TRACE_COMPONENT_CHOICES",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
