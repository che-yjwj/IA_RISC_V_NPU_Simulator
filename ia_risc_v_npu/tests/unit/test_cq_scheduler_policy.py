from src.cq import CommandQueue, CQDispatcher, SchedulingPolicy


def test_dispatcher_round_robin_balances_lanes():
    queue = CommandQueue.from_iterable(
        [
            {
                "cmd_id": "dma_a",
                "opcode": "DMA_2D",
                "operands": {"shape": [4, 4]},
            },
            {
                "cmd_id": "gemm_0",
                "opcode": "TE_GEMM",
                "operands": {"m": 4, "n": 4, "k": 4},
            },
            {
                "cmd_id": "dma_b",
                "opcode": "DMA_2D",
                "operands": {"shape": [4, 4]},
            },
            {
                "cmd_id": "gemm_1",
                "opcode": "TE_GEMM",
                "operands": {"m": 4, "n": 4, "k": 4},
            },
        ],
        strict=True,
    )

    dispatcher = CQDispatcher(policy=SchedulingPolicy.ROUND_ROBIN)
    outcome = dispatcher.run(queue)

    assert outcome.commands_executed == len(queue)
    assert outcome.trace.scheduled == ["dma_a", "gemm_0", "dma_b", "gemm_1"]
    for cmd_id in queue.command_ids():
        assert outcome.trace.states(cmd_id) == ("queued", "scheduled", "completed")
    assert outcome.stats.lane_totals == {"dma": 2, "te": 2}
    assert outcome.stats.lane_max_concurrency["dma"] == 1
    assert outcome.stats.lane_max_concurrency["te"] == 1


def test_dispatcher_edf_prioritises_earliest_deadlines():
    queue = CommandQueue.from_iterable(
        [
            {
                "cmd_id": "gemm_late",
                "opcode": "TE_GEMM",
                "operands": {"m": 4, "n": 4, "k": 4, "deadline": 40},
            },
            {
                "cmd_id": "dma_urgent",
                "opcode": "DMA_2D",
                "operands": {"shape": [4, 4], "deadline": 10},
            },
            {
                "cmd_id": "dma_follow",
                "opcode": "DMA_2D",
                "operands": {"shape": [4, 4]},
            },
        ],
        strict=True,
    )

    dispatcher = CQDispatcher(policy=SchedulingPolicy.EARLIEST_DEADLINE_FIRST)
    outcome = dispatcher.run(queue)

    assert outcome.commands_executed == len(queue)
    assert outcome.trace.scheduled == ["dma_urgent", "gemm_late", "dma_follow"]
    assert outcome.stats.lane_totals == {"dma": 2, "te": 1}
    assert outcome.stats.lane_max_concurrency["dma"] == 1
    assert outcome.stats.lane_max_concurrency["te"] == 1


def test_lane_limits_allow_parallel_scheduling():
    queue = CommandQueue.from_iterable(
        [
            {
                "cmd_id": "dma_a",
                "opcode": "DMA_2D",
                "operands": {"shape": [4, 4]},
            },
            {
                "cmd_id": "dma_b",
                "opcode": "DMA_2D",
                "operands": {"shape": [4, 4]},
            },
            {
                "cmd_id": "dma_c",
                "opcode": "DMA_2D",
                "operands": {"shape": [4, 4]},
            },
        ],
        strict=True,
    )

    dispatcher = CQDispatcher(policy=SchedulingPolicy.FIFO, lane_limits={"dma": 2})
    outcome = dispatcher.run(queue)

    waits = [
        outcome.trace.timestamps[cmd_id]["scheduled"]
        - outcome.trace.timestamps[cmd_id]["queued"]
        for cmd_id in queue.command_ids()
    ]
    assert waits[0] == 0
    assert waits[1] == 0
    assert waits[2] >= 0
    assert outcome.stats.lane_totals == {"dma": 3}
    assert outcome.stats.lane_max_concurrency["dma"] == 2
