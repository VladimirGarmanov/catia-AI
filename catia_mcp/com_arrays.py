"""Explicit SAFEARRAY output adapter; never executes injected VBA or scripts.

Some CATIA releases reject late-bound by-reference arrays. That is an explicit
capability failure, not permission to guess a return signature or return zeros.
"""
import math

from catia_mcp.runtime import CADOperationError


def read_array(method, count, *inputs):
    try:
        import pythoncom
        from win32com.client import VARIANT
    except ImportError as exc:
        raise CADOperationError("CAPABILITY_UNAVAILABLE", "SAFEARRAY adapter requires Windows pywin32") from exc
    output = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT,
                     tuple(float("nan") for _ in range(count)))
    try:
        returned = method(*inputs, output)
        values = output.value
        if returned is not None and isinstance(returned, (tuple, list)) and len(returned) == count:
            values = returned
        result = [float(value) for value in values]
        if len(result) != count or not all(math.isfinite(value) for value in result):
            raise ValueError("Output array was not populated with finite values")
        return result
    except Exception as exc:
        raise CADOperationError("CAPABILITY_UNAVAILABLE", f"CATIA SAFEARRAY output unsupported for this binding: {exc}") from exc
