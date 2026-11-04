"""Shared reader contract: exact bound member, inputs, output and errors."""
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from catia_mcp.com_arrays import read_array
from catia_mcp.runtime import CADOperationError


@pytest.fixture
def variant(monkeypatch):
    class Variant:
        def __init__(self, kind, value):
            assert kind == 0x600C
            self.value = value

    monkeypatch.setitem(sys.modules, "pythoncom", NS(
        VT_BYREF=0x4000, VT_ARRAY=0x2000, VT_VARIANT=12, DISPATCH_METHOD=1))
    monkeypatch.setitem(sys.modules, "win32com.client", NS(VARIANT=Variant))
    return Variant


@pytest.mark.parametrize("return_array", [False, True])
def test_bound_getter_preserves_input_reference_and_native_output(variant, return_array):
    other_reference = object()
    expected = tuple(float(i) for i in range(9))

    def invoke(dispid, lcid, flags, result_wanted, other, output):
        assert (dispid, lcid, flags, result_wanted) == (57, 0, 1, True)
        assert other is other_reference
        assert isinstance(output, variant)
        if return_array:
            return expected
        output.value = expected

    class Measurable:
        _oleobj_ = NS(GetIDsOfNames=Mock(return_value=57), Invoke=Mock(side_effect=invoke))

        def GetMinimumDistancePoints(self, other, output):
            pytest.fail("Do not call the type-informed wrapper or retry it")

    bound = Measurable()
    assert read_array(bound.GetMinimumDistancePoints, 9, other_reference) == list(expected)
    bound._oleobj_.GetIDsOfNames.assert_called_once_with(0, "GetMinimumDistancePoints")
    bound._oleobj_.Invoke.assert_called_once()


def test_native_error_is_preserved_without_retry_or_fallback(variant):
    class NativeError(Exception):
        hresult = -2147352567

    failure = NativeError("GetComponents failed")

    class Position:
        _oleobj_ = NS(GetIDsOfNames=Mock(return_value=42), Invoke=Mock(side_effect=failure))

        def GetComponents(self, output):
            pytest.fail("Native errors must not cause a wrapper retry")

    bound = Position()
    with pytest.raises(CADOperationError, match="GetComponents, IDispatch.Invoke, NativeError") as caught:
        read_array(bound.GetComponents, 12)
    assert caught.value.__cause__ is failure
    bound._oleobj_.Invoke.assert_called_once()


def test_plain_python_adapter_remains_supported(variant):
    def read(output):
        output.value = (1., 2., 3.)

    assert read_array(read, 3) == [1., 2., 3.]
