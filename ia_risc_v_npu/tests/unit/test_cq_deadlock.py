import pytest

from src.cq import CommandQueue, CQDispatcher
from src.cq.dispatcher import CQDeadlockError


def build_cycled_queue():
    commands = [
        {"cmd_id": "dma_a", "opcode": "DMA_2D", "deps": ["dma_c"]},
        {"cmd_id": "dma_b", "opcode": "DMA_2D", "deps": ["dma_a"]},
        {"cmd_id": "dma_c", "opcode": "DMA_2D", "deps": ["dma_b"]},
    ]
    return CommandQueue.from_iterable(commands, strict=False)


def test_cq_dispatcher_detects_dependency_cycle():
    queue = build_cycled_queue()
    dispatcher = CQDispatcher()
    with pytest.raises(CQDeadlockError):
        dispatcher.run(queue)
