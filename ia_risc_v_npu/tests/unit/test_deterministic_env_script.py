from scripts.deterministic_env import CommandResult, main as deterministic_main


def test_deterministic_main_sets_expected_env_vars():
    env: dict[str, str] = {}
    exit_code = deterministic_main(["--seed", "123"], env=env)

    assert exit_code == 0
    assert env["OPENBLAS_NUM_THREADS"] == "1"
    assert env["MKL_NUM_THREADS"] == "1"
    assert env["NUMEXPR_NUM_THREADS"] == "1"
    assert env["OMP_NUM_THREADS"] == "1"
    assert env["PYTHONHASHSEED"] == "123"


def test_deterministic_main_verify_executes_command_multiple_times():
    calls: list[tuple[tuple[str, ...], bool]] = []

    def runner(command, env, capture):
        calls.append((tuple(command), capture))
        return CommandResult(returncode=0, stdout="stable", stderr="")

    exit_code = deterministic_main([
        "--seed",
        "7",
        "--repeat",
        "3",
        "--verify",
        "--",
        "echo",
        "hi",
    ], env={}, runner=runner)

    assert exit_code == 0
    assert len(calls) == 3
    assert all(capture for _, capture in calls)
    assert all(command == ("echo", "hi") for command, _ in calls)


def test_deterministic_main_verify_detects_output_mismatch():
    responses = [
        CommandResult(returncode=0, stdout="first", stderr=""),
        CommandResult(returncode=0, stdout="second", stderr=""),
    ]

    def runner(command, env, capture):
        return responses.pop(0)

    exit_code = deterministic_main([
        "--repeat",
        "2",
        "--verify",
        "--",
        "echo",
        "hi",
    ], env={}, runner=runner)

    assert exit_code == 3
