"""Reproduce typed-wrapper SAFEARRAY rejection without pywin32 or CATIA."""
import json
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from catia_mcp.server import CATIAMCPServer


IDENTITY = [1., 0, 0, 0, 1., 0, 0, 0, 1., 5, 6, 7]


class Variant:
    def __init__(self, kind, value):
        assert kind == 0x600C  # BYREF | ARRAY | VARIANT
        self.value = value


@pytest.fixture
def rig(monkeypatch):
    monkeypatch.setitem(sys.modules, "pythoncom", NS(
        VT_BYREF=0x4000, VT_ARRAY=0x2000, VT_VARIANT=12, DISPATCH_METHOD=1))
    client = NS(VARIANT=Variant)
    monkeypatch.setitem(sys.modules, "win32com", NS(client=client))
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    pose = list(IDENTITY)
    def read(output):
        if isinstance(output, Variant):
            output.value = tuple(pose)
        # Ordinary list is deliberately unchanged: late binding lost the out value.
    class Position:
        def __init__(self):
            self._oleobj_ = NS(GetIDsOfNames=Mock(return_value=42),
                               Invoke=Mock(side_effect=self.invoke))
            self.SetComponents = Mock(side_effect=lambda values: pose.__setitem__(slice(None), values))

        def GetComponents(self, output):
            if isinstance(output, Variant):
                # Exact Windows failure: the generated/type-informed wrapper
                # expects a Python sequence and rejects VARIANT before COM.
                raise TypeError("Objects for SAFEARRAYS must be sequences (of sequences), or a buffer object.")
            # A plain input list is unchanged, as in the original bug.

        def invoke(self, dispid, lcid, flags, result_wanted, output):
            assert (dispid, lcid, flags, result_wanted) == (42, 0, 1, True)
            return read(output)

    position = Position()
    component = NS(Name="PULLEY.1", PartNumber="PULLEY", Position=position)
    product = NS(Products=NS(Count=1, Item=lambda _: component), Update=Mock())
    document = NS(Name="Assembly.CATProduct", Product=product)
    server = CATIAMCPServer()
    server.connection.app = NS(ActiveDocument=document, Documents=NS(Count=1, Item=lambda _: document))
    server.connection.ensure_connected = Mock()
    server.connection.refresh_display = Mock()
    server.session.bind()
    args = {"component_name": "PULLEY.1", "tx": 0, "ty": 0, "tz": 0,
            "rx": 0, "ry": 0, "rz": 0, "document_id": server.session.document_id(),
            "expected_revision": 0, "request_id": "move-1"}
    yield NS(server=server, pose=pose, position=position, product=product, args=args)
    server.worker.shutdown()


def test_zero_move_reads_byref_without_mutation_update_or_revision(rig):
    ignored_list = [0.] * 12
    rig.position.GetComponents(ignored_list)
    assert ignored_list == [0.] * 12  # The previous code diagnosed these zeros as a bad pose.
    with pytest.raises(TypeError, match="Objects for SAFEARRAYS must be sequences"):
        rig.position.GetComponents(Variant(0x600C, tuple(ignored_list)))
    result = rig.server._execute_serial("catia_move_component", rig.args)
    assert result["ok"] and result["changed"] is False
    assert result["axis_components"] == IDENTITY
    assert result["session"]["revision"] == 0 and result["updated"] is False
    rig.position.SetComponents.assert_not_called()
    rig.product.Update.assert_not_called()
    rig.position._oleobj_.GetIDsOfNames.assert_called_once_with(0, "GetComponents")
    rig.position._oleobj_.Invoke.assert_called_once()


def test_real_increment_uses_existing_rotation_and_is_not_replayed(rig):
    rig.pose[:9] = [0., 1, 0, -1, 0, 0, 0, 0, 1]
    args = {**rig.args, "tx": 10, "rz": 90}
    first = rig.server._execute_serial("catia_move_component", args)
    assert first["ok"] and first["changed"] and first["updated"]
    assert first["axis_components"] == pytest.approx([-1, 0, 0, 0, -1, 0, 0, 0, 1, 15, 6, 7])
    assert first["modified_handles"] and first["session"]["revision"] == 1
    assert rig.server._execute_serial("catia_move_component", args)["replayed"]
    rig.position.SetComponents.assert_called_once()
    rig.product.Update.assert_called_once()


@pytest.mark.parametrize("mode,code", [("unpopulated", "POSITION_UNAVAILABLE"),
                                      ("mirrored", "INVALID_COMPONENT_POSE"),
                                      ("zeros", "INVALID_COMPONENT_POSE")])
def test_unreadable_or_invalid_pose_fails_before_any_mutation(rig, mode, code):
    if mode == "unpopulated":
        rig.position._oleobj_.Invoke.side_effect = lambda *args: None
    elif mode == "mirrored":
        rig.pose[0] = -1
    else:
        rig.pose[:] = [0.] * 12
    result = rig.server._execute_serial("catia_move_component", {**rig.args, "tx": 10})
    assert result["code"] == code and result["status"] == "failed"
    assert not result["session"]["reconciliation_required"] and result["session"]["revision"] == 0
    rig.position.SetComponents.assert_not_called()
    rig.product.Update.assert_not_called()
    listed = json.loads(rig.server.assembly_tools._list_components())
    assert listed[0]["position"] is None and listed[0]["position_error"]["code"] == code


@pytest.mark.parametrize("failure,code", [("update", "UPDATE_FAILED"), ("solver", "POSTCONDITION_FAILED")])
def test_failure_after_input_remains_partial_and_is_not_repeated(rig, failure, code):
    if failure == "update":
        rig.product.Update.side_effect = RuntimeError("solve failed")
    else:
        rig.product.Update.side_effect = lambda: rig.pose.__setitem__(9, IDENTITY[9])
    args = {**rig.args, "tx": 10}
    result = rig.server._execute_serial("catia_move_component", args)
    assert result["code"] == code and result["status"] == "partial_failure"
    assert result["session"]["reconciliation_required"]
    assert rig.server._execute_serial("catia_move_component", args)["replayed"]
    rig.position.SetComponents.assert_called_once()
