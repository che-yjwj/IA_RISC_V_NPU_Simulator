"""Command-line helper for locking the simulator into deterministic mode."""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, MutableMapping, Sequence

from src.simulator.determinism import configure_deterministic_environment, DeterminismConfig


@dataclass(slots=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


Runner = Callable[[Sequence[str], MutableMapping[str, str], bool], CommandResult]


def _subprocess_runner(
    command: Sequence[str], env: MutableMapping[str, str], capture: bool
) -> CommandResult:
    completed = subprocess.run(
        command,
        check=False,
        env=dict(env),
        text=True,
        capture_output=capture,
    )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply deterministic environment guards (BLAS threads, RNG seed) "
            "and optionally execute a command multiple times to verify "
            "repeatability."
        )
    )
    parser.add_argument("--seed", type=int, default=0, help="Seed for deterministic RNGs")
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Run the command N times after configuring the environment",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Capture stdout/stderr and assert they are identical across runs",
    )
    parser.add_argument(
        "--show-env",
        action="store_true",
        help="Print the enforced environment variables after configuration",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to execute after '--'. Example: -- pytest -q",
    )
    return parser.parse_args(argv)


def _print_env_snapshot(env: MutableMapping[str, str], config: DeterminismConfig) -> None:
    interesting = list(config.thread_env_vars) + ["PYTHONHASHSEED"]
    for key in interesting:
        value = env.get(key, "<unset>")
        print(f"{key}={value}")


def main(
    argv: Sequence[str] | None = None,
    *,
    env: MutableMapping[str, str] | None = None,
    runner: Runner | None = None,
    config: DeterminismConfig | None = None,
) -> int:
    args = _parse_args(argv)
    target_env = env if env is not None else os.environ
    active_config = config or DeterminismConfig(seed=args.seed)
    configure_deterministic_environment(
        seed=args.seed,
        env=target_env,
        force=True,
        config=active_config,
    )

    if args.show_env:
        _print_env_snapshot(target_env, active_config)

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]

    if not command:
        return 0

    if args.repeat < 1:
        print("--repeat must be a positive integer", file=sys.stderr)
        return 2

    command_runner = runner or _subprocess_runner

    if args.verify:
        baseline_stdout: str | None = None
        baseline_stderr: str | None = None
        baseline_hash: str | None = None
        for iteration in range(args.repeat):
            result = command_runner(command, target_env, True)
            if result.returncode != 0:
                print(
                    f"Run {iteration + 1} failed with exit code {result.returncode}",
                    file=sys.stderr,
                )
                return result.returncode

            digest = hashlib.sha256(result.stdout.encode("utf-8")).hexdigest()
            if baseline_hash is None:
                baseline_stdout = result.stdout
                baseline_stderr = result.stderr
                baseline_hash = digest
                continue

            if result.stdout != baseline_stdout or result.stderr != baseline_stderr:
                print(
                    "Captured output differed between runs; determinism check failed",
                    file=sys.stderr,
                )
                return 3

            if digest != baseline_hash:
                print(
                    "Hash mismatch between runs despite identical text capture",
                    file=sys.stderr,
                )
                return 3

        print(
            f"Determinism verified over {args.repeat} runs "
            f"(sha256={baseline_hash})."
        )
        return 0

    for iteration in range(args.repeat):
        result = command_runner(command, target_env, False)
        if result.returncode != 0:
            print(
                f"Run {iteration + 1} failed with exit code {result.returncode}",
                file=sys.stderr,
            )
            return result.returncode

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
