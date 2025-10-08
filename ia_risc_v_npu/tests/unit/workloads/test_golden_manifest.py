import pytest

from workloads.golden import GOLDEN_WORKLOADS, iter_workloads


def test_manifest_contains_expected_entries():
    workload_ids = tuple(GOLDEN_WORKLOADS.keys())
    assert len(workload_ids) == 5
    assert set(workload_ids) == {
        "cq_dma_roundtrip",
        "cq_dma_chain",
        "cq_gemm_single",
        "cq_gemm_pipeline",
        "cq_mixed_latency",
    }


@pytest.mark.parametrize("workload", tuple(iter_workloads()))
def test_plan_paths_exist(workload):
    plan_path = workload.plan_path()
    assert plan_path.is_file(), f"Missing plan file for {workload.workload_id}"
    assert plan_path.suffix == ".yaml"
    trace_path = workload.trace_path()
    assert trace_path.is_file(), f"Missing trace file for {workload.workload_id}"
    assert trace_path.suffix == ".jsonl"
    config_path = workload.config_path()
    assert config_path.is_file(), f"Missing config file for {workload.workload_id}"
    assert config_path.suffix == ".json"


def test_manifest_exports_json_friendly_payload():
    payloads = [entry.as_dict() for entry in iter_workloads()]
    assert all("workload_id" in payload for payload in payloads)
    assert all(isinstance(payload.get("tags"), list) for payload in payloads)
    assert all(isinstance(payload.get("plan_path"), str) for payload in payloads)
    assert all(isinstance(payload.get("trace_path"), str) for payload in payloads)
    assert all(isinstance(payload.get("config_path"), str) for payload in payloads)
