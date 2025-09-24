from __future__ import annotations

from src.simulator.main import AdaptiveSimulator
from src.simulator.program import ProgramImage, ProgramSegment


def test_load_program_respects_segment_layout():
    simulator = AdaptiveSimulator()
    data = b"\x01\x02\x03\x04"
    segment = ProgramSegment(address=0x100, data=data, mem_size=len(data) + 4)
    image = ProgramImage(
        instructions=[int.from_bytes(data, "little")],
        text_size=len(data),
        entry_point=0x100,
        segments=[segment],
    )

    simulator.load_program(image)

    assert simulator.risc_v_engine.pc == 0x100
    assert simulator.bus.read(0x100, len(data)) == data
    assert simulator.bus.read(0x104, 4) == b"\x00" * 4


def test_load_program_accepts_word_iterable():
    simulator = AdaptiveSimulator()
    words = [0x11223344, 0x55667788]

    simulator.load_program(words, base_address=0x200)

    assert simulator.risc_v_engine.pc == 0x200
    expected_bytes = b"".join(word.to_bytes(4, "little") for word in words)
    assert simulator.bus.read(0x200, len(expected_bytes)) == expected_bytes
