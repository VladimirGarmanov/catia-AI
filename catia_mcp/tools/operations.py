"""Shared contracts for manually implemented operation groups, not COM dispatch APIs."""
from __future__ import annotations

import math

from catia_mcp.runtime import CADOperationError
from catia_mcp.tools.engineering import HANDLE, NUMBER, tool


BOOL = {"type": "boolean"}
INTEGER = {"type": "integer"}


def array(item, minimum=1, maximum=None):
    result = {"type": "array", "items": item, "minItems": minimum}
    if maximum is not None:
        result["maxItems"] = maximum
    return result


VECTOR = array(NUMBER, 3, 3)
POINT = {"point", "vertex"}
CURVE = {"line", "curve", "edge", "line2d", "circle2d"}
LINE = {"line", "line2d", "edge"}
SURFACE = {"surface", "face", "plane"}


def group(name, description, modes, common=None, readonly=False):
    """An explicit mode discriminator rejects fields irrelevant to that mode."""
    common = common or {}
    properties = {"mode": {"enum": list(modes)}, **common}
    alternatives = []
    for mode, fields in modes.items():
        properties.update(fields)
        allowed = {"mode", *common, *fields, "document_id", "request_id", "expected_revision"}
        alternatives.append({"properties": {"mode": {"const": mode}},
                             "required": list(fields),
                             "propertyNames": {"enum": sorted(allowed)}})
    result = tool(name, description, properties, ["mode", *common], readonly)
    result["inputSchema"]["oneOf"] = alternatives
    return result


def unit_vector(values):
    magnitude = math.sqrt(sum(v * v for v in values))
    if magnitude < 1e-12:
        raise CADOperationError("INVALID_ARGUMENT", "Direction must be nonzero")
    return tuple(v / magnitude for v in values)


class OperationTools:
    strict_writes = True

    def __init__(self, engineering):
        self.engineering = engineering
        self.conn = engineering.conn

    @property
    def state(self):
        return self.engineering.state

    def obj(self, handle, kinds):
        return self.state.resolve(handle, kinds).value

    def ref(self, handle, kinds):
        return self.state.reference(handle, kinds)

    def changed(self, handle):
        self.state.resolve(handle)
        self.state.mutation_started = True
        if handle not in self.state.modified:
            self.state.modified.append(handle)

    def finish(self, value, kind="feature", container=None):
        return self.engineering.finish(value, kind, {}, container)

    def update(self, owner):
        try:
            owner.Update()
        except Exception as exc:
            raise CADOperationError("UPDATE_FAILED", str(exc)) from exc
        self.state.updated = True
        return {"ok": True, "updated": True,
                "verification": "Update completed; independent geometry verification NOT performed"}
