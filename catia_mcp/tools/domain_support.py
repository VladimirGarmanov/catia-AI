"""Small collection/readback helpers for Product and Drawing tools."""
import math

from catia_mcp.runtime import CADOperationError, same_object


def members(collection):
    for index in range(1, int(collection.Count) + 1):
        yield index, collection.Item(index)


def member_index(collection, value):
    for index, candidate in members(collection):
        if same_object(candidate, value):
            return index
    raise CADOperationError("STALE_REFERENCE", "Object is not a member of the specified owner; reread domain objects")


def read_properties(obj, fields):
    """Optional COM properties must be reported unavailable, never invented."""
    result, unavailable = {}, {}
    for name, convert in fields.items():
        try:
            result[name] = convert(getattr(obj, name))
        except Exception as exc:
            result[name] = None
            unavailable[name] = str(exc)
    if unavailable:
        result["unavailable"] = unavailable
    return result


def verify_equal(actual, expected, label):
    if isinstance(expected, (float, int)) and not isinstance(expected, bool):
        equal = math.isclose(float(actual), expected, rel_tol=1e-8, abs_tol=1e-7)
    else:
        equal = actual == expected
    if not equal:
        raise CADOperationError("POSTCONDITION_FAILED", f"{label}: expected {expected!r}, read back {actual!r}; inspect before another write")
