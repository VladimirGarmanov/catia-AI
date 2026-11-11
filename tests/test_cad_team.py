"""Actual local input preparation and task scheduling; no model or COM calls."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from scripts.cad_team import TeamBoard, prepare_bundle, read_json


@pytest.fixture
def bundle(tmp_path):
    from PIL import Image
    paths = []
    for index in range(5):
        folder = tmp_path / str(index)
        folder.mkdir()
        path = folder / "drawing.png"  # Duplicate basenames must remain distinct.
        with Image.new("RGB", (24, 16), (index * 40, 0, 0)) as image:
            image.save(path)
        paths.append(path)
    return TeamBoard(prepare_bundle(paths, tmp_path / "team"))


def report(ready=True):
    return {"summary": "Read dimensions", "plan": "Create a dimensioned profile then pad",
            "checks": ["Read back pad length"], "questions": [] if ready else ["Which thickness?"],
            "ready": ready}


def finish(board, task_id, owner="worker"):
    current = board.state(task_id)
    claimed = board.claim(task_id, owner, current["revision"])
    return board.submit(task_id, owner, claimed["revision"], report())


def test_five_files_are_isolated_and_can_be_planned_concurrently(bundle):
    files = bundle.manifest["files"]
    assert len(files) == 5 and len({row["snapshot"] for row in files}) == 5
    assert all(Path(row["pages"][0]).is_file() for row in files)
    assert [row["task_id"] for row in files] == [f"file_{i:03}" for i in range(1, 6)]
    assert all(Path(row["source"]).read_bytes() == Path(row["snapshot"]).read_bytes() for row in files)
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda row: finish(bundle, row["task_id"], row["task_id"]), files))
    assert all(result["status"] == "completed" for result in results)
    assert not bundle.status()["planning_complete"]
    finish(bundle, "integrate", "planner")
    finish(bundle, "review", "reviewer")
    assert bundle.status()["planning_complete"]
    assert bundle.status()["cad_verified"] is False


def test_dependencies_wrong_owner_and_stale_worker_are_rejected(bundle):
    with pytest.raises(ValueError, match="Dependency"):
        bundle.claim("integrate", "planner", 0)
    state = bundle.claim("file_001", "alice", 0)
    with pytest.raises(ValueError, match="owner"):
        bundle.submit("file_001", "bob", state["revision"], report())
    with pytest.raises(ValueError, match="claimed"):
        bundle.claim("file_001", "bob", state["revision"])
    bundle.reset("file_001", state["revision"], {"human_answer": "Thickness is 5mm"})
    with pytest.raises(ValueError, match="stale revision"):
        bundle.submit("file_001", "alice", state["revision"], report())
    assert bundle.packet("file_001")["state"]["context"]["human_answer"] == "Thickness is 5mm"


def test_reset_invalidates_integration_and_review_transitively(bundle):
    for row in bundle.manifest["files"]:
        finish(bundle, row["task_id"])
    finish(bundle, "integrate")
    finish(bundle, "review")
    bundle.reset("file_001", bundle.state("file_001")["revision"])
    statuses = {row["task_id"]: row for row in bundle.status()["tasks"]}
    assert statuses["integrate"]["stale"] and statuses["review"]["stale"]
    assert not bundle.status()["planning_complete"]


def test_changed_source_and_unanswered_questions_prevent_completion(bundle):
    claimed = bundle.claim("file_001", "reader", 0)
    blocked = bundle.submit("file_001", "reader", claimed["revision"], report(False))
    assert blocked["status"] == "blocked"
    with pytest.raises(ValueError, match="Dependency"):
        bundle.claim("integrate", "planner", 0)
    Path(bundle.manifest["files"][0]["source"]).write_bytes(b"changed source")
    assert bundle.status()["changed_sources"] == ["file_001"]
    with pytest.raises(ValueError, match="Source files changed"):
        bundle.claim("file_001", "reader", blocked["revision"])


def test_cad_binary_is_context_only_and_preparation_failure_has_no_manifest(tmp_path):
    cad = tmp_path / "Part.CATPart"
    cad.write_bytes(b"opaque CAD binary; not parsed")
    board = TeamBoard(prepare_bundle([cad], tmp_path / "out"))
    assert board.manifest["files"][0]["pages"] == []
    claimed = board.claim("file_001", "inspector", 0)
    with pytest.raises(ValueError, match="coordinator-provided context"):
        board.submit("file_001", "inspector", claimed["revision"], report())
    bad = tmp_path / "corrupt.pdf"
    bad.write_bytes(b"not a pdf")
    with pytest.raises(ValueError):
        prepare_bundle([cad, bad], tmp_path / "failed")
    assert not list((tmp_path / "failed").rglob("manifest.json"))
    with pytest.raises(ValueError, match="more than once"):
        prepare_bundle([cad, cad], tmp_path / "duplicates")


def test_report_protocol_does_not_accept_questions_as_ready(bundle):
    state = bundle.claim("file_001", "reader", 0)
    invalid = {**report(), "questions": ["Missing dimension"]}
    with pytest.raises(ValueError, match="unresolved questions"):
        bundle.submit("file_001", "reader", state["revision"], invalid)
    assert read_json(bundle.task_path("file_001"))["status"] == "in_progress"


def test_worker_program_must_compile_offline(bundle, tmp_path):
    from scripts.cad_team import main
    good = {"title": "plate", "steps": [
        {"id": "sk", "tool": "catia_create_sketch", "args": {"plane": "xy"}},
        {"id": "pad", "tool": "catia_pad", "args": {"height": 8, "sketch_handle": {"$ref": "sk.handle"}}}]}
    bad = {"steps": [{"id": "pad", "tool": "catia_pad", "args": {"height": "eight"}}]}
    board_state = bundle.claim("file_001", "worker", 0)
    with pytest.raises(ValueError, match="program does not compile"):
        bundle.submit("file_001", "worker", board_state["revision"], dict(report(), program=bad))
    done = bundle.submit("file_001", "worker", board_state["revision"], dict(report(), program=good))
    assert done["status"] == "completed" and done["report"]["program_id"].startswith("plan_")
    path = tmp_path / "plan.json"
    path.write_text(__import__("json").dumps(bad))
    assert main(["compile", str(path)]) == 1
