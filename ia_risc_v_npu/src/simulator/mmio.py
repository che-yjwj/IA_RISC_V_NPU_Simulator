"""Memory-mapped I/O facade for the NPU cluster."""

from __future__ import annotations

from typing import Dict, Optional

from src.npu.cluster import ClusterPolicy, ClusterTask, NPUCluster, SubmissionResult


class MMIO:
    """Minimal MMIO device that can launch NPU cluster work via registers."""

    REG_INPUT_ADDR = 0x00
    REG_INPUT_SIZE = 0x04
    REG_OUTPUT_ADDR = 0x08
    REG_OUTPUT_SIZE = 0x0C
    REG_COMPUTE_CYCLES = 0x10
    REG_ISSUE_AT = 0x14
    REG_POLICY = 0x18
    REG_CONTROL = 0x1C
    REG_STATUS = 0x20
    REG_LAST_DONE = 0x24
    REG_LAST_CORE = 0x28

    CONTROL_LAUNCH = 0x1

    def __init__(self, cluster: NPUCluster) -> None:
        self.cluster = cluster
        self._registers: Dict[int, int] = {
            self.REG_INPUT_ADDR: 0,
            self.REG_INPUT_SIZE: 0,
            self.REG_OUTPUT_ADDR: 0,
            self.REG_OUTPUT_SIZE: 0,
            self.REG_COMPUTE_CYCLES: 0,
            self.REG_ISSUE_AT: 0,
            self.REG_POLICY: 0,
            self.REG_CONTROL: 0,
            self.REG_STATUS: 0,
            self.REG_LAST_DONE: 0,
            self.REG_LAST_CORE: 0,
        }
        self._last_submission: Optional[SubmissionResult] = None
        # Provide compatibility with legacy behaviour that exposed NPU registers.
        self._fallback_registers = cluster.compute_engine.internal_registers

    @property
    def last_submission(self) -> Optional[SubmissionResult]:
        return self._last_submission

    def read(self, address: int, size: int) -> bytes:
        value = self._registers.get(address)
        if address == self.REG_LAST_DONE and self._last_submission is not None:
            done_at = self._last_submission.done_at
            if done_at >= 0:
                value = self._registers[address] = done_at
        elif address == self.REG_LAST_CORE and self._last_submission is not None:
            value = self._registers[address] = self._last_submission.core_id
        if value is None:
            value = self._fallback_registers.get(address, 0)
        return int(value & 0xFFFFFFFF).to_bytes(size, byteorder="little", signed=False)

    def write(self, address: int, data: bytes) -> None:
        value = int.from_bytes(data, byteorder="little", signed=False)
        if address not in self._registers:
            self._fallback_registers[address] = value
            return

        self._registers[address] = value
        if address == self.REG_CONTROL and value & self.CONTROL_LAUNCH:
            self._launch_task()

    def _launch_task(self) -> None:
        policy_value = self._registers[self.REG_POLICY]
        policy = ClusterPolicy.ROUND_ROBIN if policy_value == 1 else ClusterPolicy.MIN_FINISH_TIME

        issue_at = self._registers[self.REG_ISSUE_AT]
        issue_at = max(issue_at, self.cluster.bus.now)

        task = ClusterTask(
            name=f"mmio:{len(self.cluster.history) + 1}",
            input_bytes=self._registers[self.REG_INPUT_SIZE],
            output_bytes=self._registers[self.REG_OUTPUT_SIZE],
            compute_cycles=self._registers[self.REG_COMPUTE_CYCLES],
            issue_at=issue_at,
            input_address=self._registers[self.REG_INPUT_ADDR],
            output_address=self._registers[self.REG_OUTPUT_ADDR],
        )

        result = self.cluster.submit(task, policy=policy)
        self._last_submission = result

        self._registers[self.REG_STATUS] = 0
        self._registers[self.REG_LAST_DONE] = result.done_at
        self._registers[self.REG_LAST_CORE] = result.core_id
        self._registers[self.REG_CONTROL] = 0


__all__ = ["MMIO"]
