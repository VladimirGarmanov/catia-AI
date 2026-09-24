"""Active CATIA context and an exact, selected-feature update action.

Names and selection positions are display context, never durable face/edge IDs.
"""

from __future__ import annotations

import json
import ntpath
from typing import Any

from catia_mcp.connection import CATIAConnection
from catia_mcp.tools.document import DocumentTools


class ContextTools:
    """Read the current document/selection and update one selected feature."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection
        self.documents = DocumentTools(connection)

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "catia_get_selection",
                "description": (
                    "Read the current CATIA selection: count, available element types/names, "
                    "and document context. Names and positions are not stable face/edge IDs."
                ),
                "inputSchema": {"type": "object", "properties": {}},
                "readOnlyHint": True,
            },
            {
                "name": "catia_get_model_state",
                "description": (
                    "Read the active document, bodies/sketches/features or components, "
                    "parameters, and the current selection. This is not geometry verification."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "max_parameters": {
                            "type": "integer", "minimum": 0, "maximum": 500,
                            "default": 100,
                            "description": (
                                "Maximum number of parameters returned "
                                "(0 to omit them)."
                            ),
                        },
                    },
                },
                "readOnlyHint": True,
            },
            {
                "name": "catia_update_selected_feature",
                "description": (
                    "Update exactly one currently selected Part feature or sketch by its "
                    "live CATIA COM object. Does not use a name or topology index, "
                    "and does not save."
                ),
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in {
            "catia_get_selection", "catia_get_model_state", "catia_update_selected_feature",
        }:
            raise ValueError(f"Unknown context tool: {tool_name}")
        if not self.conn.is_connected:
            return self._error("NOT_CONNECTED", "Connect to CATIA with catia_connect first")
        try:
            doc = self.conn.active_document
        except Exception as exc:
            return self._error("NO_ACTIVE_DOCUMENT", f"Cannot read active CATIA document: {exc}")

        if tool_name == "catia_update_selected_feature":
            return self._update_selected_feature(doc)

        try:
            selection = self._read_selection(doc)
        except Exception as exc:
            return self._error("SELECTION_READ_FAILED", f"Cannot read CATIA selection: {exc}")

        if tool_name == "catia_get_selection":
            return self._success({
                "document": self._document_label(doc),
                "selection": selection,
            })

        max_parameters = arguments.get("max_parameters", 100)
        if (
            isinstance(max_parameters, bool)
            or not isinstance(max_parameters, int)
            or not 0 <= max_parameters <= 500
        ):
            return self._error(
                "INVALID_ARGUMENT", "max_parameters must be an integer from 0 to 500"
            )

        try:
            document_info = json.loads(self.documents._get_active_document_info(doc))
        except Exception as exc:
            return self._error("MODEL_STATE_READ_FAILED", f"Cannot inspect active model: {exc}")
        data: dict[str, Any] = {"document": document_info, "selection": selection}
        if document_info["type"] == "CATPart":
            try:
                data["parameters"] = self._read_parameters(doc.Part, max_parameters)
            except Exception as exc:
                return self._error("MODEL_STATE_READ_FAILED", f"Cannot inspect parameters: {exc}")
        return self._success(data)

    @staticmethod
    def _error(code: str, message: str) -> dict[str, Any]:
        return {"ok": False, "code": code, "message": message}

    @staticmethod
    def _success(data: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "code": "OK", "data": data}

    @staticmethod
    def _optional_attr(
        obj: Any, name: str, warnings: list[str] | None = None, label: str | None = None
    ) -> Any | None:
        try:
            return getattr(obj, name)
        except AttributeError:
            return None
        except Exception as exc:
            if warnings is not None:
                warnings.append(f"{label or name} could not be read: {exc}")
            return None

    def _document_label(self, doc: Any) -> dict[str, str | None]:
        return {
            "name": self._optional_attr(doc, "Name"),
            "path": self._optional_attr(doc, "FullName"),
        }

    @staticmethod
    def _dimension_value(dimension: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        try:
            display = dimension.ValueAsString
            result["display"] = str(display() if callable(display) else display)
        except Exception:
            pass
        try:
            raw = dimension.Value
            if isinstance(raw, (int, float, str, bool)):
                result["raw_value"] = raw
        except Exception:
            pass
        return result

    def _feature_dimensions(self, value: Any) -> dict[str, dict[str, Any]]:
        dimensions: dict[str, dict[str, Any]] = {}
        paths = {
            "first_limit": ("FirstLimit", "Dimension"),
            "second_limit": ("SecondLimit", "Dimension"),
            "diameter": ("Diameter",),
            "radius": ("Radius",),
            "length1": ("Length1",),
            "angle": ("Angle",),
        }
        for label, path in paths.items():
            current = value
            for attribute in path:
                current = self._optional_attr(current, attribute)
                if current is None:
                    break
            if current is not None:
                measured = self._dimension_value(current)
                if measured:
                    dimensions[label] = measured
        return dimensions

    def _read_parameters(self, part: Any, limit: int) -> dict[str, Any]:
        parameters = part.Parameters
        total = parameters.Count
        items: list[dict[str, Any]] = []
        for index in range(1, min(total, limit) + 1):
            parameter = parameters.Item(index)
            item = {"name": str(parameter.Name)}
            item.update(self._dimension_value(parameter))
            items.append(item)
        return {"total": total, "returned": len(items), "truncated": len(items) < total,
                "items": items}

    def _update_selected_feature(self, doc: Any) -> dict[str, Any]:
        # Capture one live COM object; a second Item2 lookup could select a
        # different feature of the same type. This is not a persistent ID.
        try:
            selection = doc.Selection
            count = selection.Count2
            selected = selection.Item2(1) if count == 1 else None
        except Exception as exc:
            return self._error("SELECTION_READ_FAILED", f"Cannot read CATIA selection: {exc}")
        if count == 0:
            return self._error("EMPTY_SELECTION", "Select one Part feature or sketch first")
        if count != 1:
            return self._error("MULTIPLE_SELECTION", "Select exactly one Part feature or sketch")
        try:
            part = doc.Part
        except Exception:
            return self._error("WRONG_DOCUMENT_TYPE", "The active document is not a CATPart")
        try:
            owner = self._optional_attr(selected, "Document")
            if owner is not None:
                active_path = self._optional_attr(doc, "FullName")
                owner_path = self._optional_attr(owner, "FullName")
                if (
                    active_path and owner_path
                    and ntpath.normcase(ntpath.normpath(str(active_path)))
                    != ntpath.normcase(ntpath.normpath(str(owner_path)))
                ):
                    return self._error(
                        "DIFFERENT_DOCUMENT",
                        "The selected object belongs to another document; no update was made",
                    )
            selected_type = str(selected.Type)
            if selected_type not in {
                "Pad", "Prism", "Pocket", "Sketch", "Hole", "Shaft", "Groove",
                "Chamfer", "EdgeFillet", "Fillet",
            }:
                return self._error(
                    "UNSUPPORTED_SELECTION_TYPE",
                    f"Selected type {selected_type!r} is not a supported feature/sketch",
                )
            value = selected.Value
            name = str(value.Name)
            part.UpdateObject(value)
            part.Update()
            if not part.IsUpToDate(value):
                return self._error("UPDATE_FAILED", f"CATIA reports {name!r} is not up to date")
        except Exception as exc:
            return self._error("UPDATE_FAILED", f"Could not update selected feature: {exc}")
        return self._success({"feature": name, "selection_type": selected_type,
                              "up_to_date": True, "saved": False})

    def _read_selection(self, doc: Any) -> dict[str, Any]:
        selection = doc.Selection
        try:
            count = selection.Count2
            item_at = selection.Item2
        except AttributeError:
            # Older CATIA Automation versions may only expose Count/Item.
            count = selection.Count
            item_at = selection.Item

        items: list[dict[str, Any]] = []
        warnings: list[str] = []
        for position in range(1, count + 1):
            try:
                selected = item_at(position)
            except Exception as exc:
                raise RuntimeError(
                    f"Selection position {position} could not be read: {exc}"
                ) from exc

            item: dict[str, Any] = {"position": position}
            selected_type = self._optional_attr(
                selected, "Type", warnings, f"Selection position {position} type")
            if selected_type is not None:
                item["selection_type"] = str(selected_type)

            value = self._optional_attr(
                selected, "Value", warnings, f"Selection position {position} value")
            if value is not None:
                name = self._optional_attr(
                    value, "Name", warnings, f"Selection position {position} name")
                if name is not None:
                    item["name"] = str(name)
                value_type = self._optional_attr(
                    value, "Type", warnings, f"Selection position {position} value type")
                if value_type is not None:
                    item["value_type"] = str(value_type)
                dimensions = self._feature_dimensions(value)
                if dimensions:
                    item["dimensions"] = dimensions

            owner = self._optional_attr(
                selected, "Document", warnings, f"Selection position {position} document")
            if owner is not None:
                item["document"] = self._document_label(owner)

            leaf_product = self._optional_attr(
                selected, "LeafProduct", warnings, f"Selection position {position} leaf product")
            if leaf_product is not None:
                product_name = self._optional_attr(
                    leaf_product, "Name", warnings,
                    f"Selection position {position} leaf product name")
                if product_name is not None:
                    item["leaf_product_name"] = str(product_name)
            items.append(item)

        return {
            "count": count,
            "items": items,
            "warnings": warnings,
            "identity_note": (
                "Positions and names describe the current selection only; "
                "they are not persistent or exact face/edge references."
            ),
        }
