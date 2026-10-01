"""Assembly tools for CATIA V5.

Product/Assembly management: add components, constraints (Fix, Coincidence,
Contact, Offset, Angle), move components, and manage the product tree.
"""

from __future__ import annotations

import json
import math
import ntpath
from pathlib import Path
from typing import Any

from catia_mcp.connection import CATIAConnection


class AssemblyTools:
    """Tools for assembly (Product) operations in CATIA V5."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "catia_add_component",
                "description": (
                    "Add an existing CATPart or CATProduct file as a component in the active assembly. "
                    "The component is inserted at the origin."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Full path to the .CATPart or .CATProduct file to add",
                        },
                    },
                    "required": ["file_path"],
                },
            },
            {
                "name": "catia_add_new_part",
                "description": (
                    "Create a new empty Part directly inside the active assembly. "
                    "Returns the name of the created component."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name for the new part component",
                        },
                    },
                },
            },
            {
                "name": "catia_fix_constraint",
                "description": (
                    "Fix the one currently selected assembly instance in place. "
                    "Selection must be the component Product itself, not a face or feature."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component_name": {
                            "type": "string",
                            "description": "Name of the component to fix",
                        },
                    },
                    "required": ["component_name"],
                },
            },
            {
                "name": "catia_coincidence_constraint",
                "description": (
                    "Constrain two currently selected exact assembly supports in selection order. "
                    "Each selected support must belong to the named component; names do not "
                    "resolve face or plane references."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component1": {
                            "type": "string",
                            "description": "Name of first component",
                        },
                        "component2": {
                            "type": "string",
                            "description": "Name of second component",
                        },
                        "element1": {
                            "type": "string",
                            "description": "Unsupported legacy name target; select exact geometry instead",
                        },
                        "element2": {
                            "type": "string",
                            "description": "Unsupported legacy name target; select exact geometry instead",
                        },
                    },
                    "required": ["component1", "component2"],
                },
            },
            {
                "name": "catia_offset_constraint",
                "description": (
                    "Create an Offset constraint between two faces/planes of two components. "
                    "Select both exact assembly supports in order before calling."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component1": {
                            "type": "string",
                            "description": "Name of first component",
                        },
                        "component2": {
                            "type": "string",
                            "description": "Name of second component",
                        },
                        "offset": {
                            "type": "number",
                            "description": "Offset distance in mm",
                        },
                    },
                    "required": ["component1", "component2", "offset"],
                },
            },
            {
                "name": "catia_angle_constraint",
                "description": "Create an Angle constraint between two exact selected assembly supports.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component1": {
                            "type": "string",
                            "description": "Name of first component",
                        },
                        "component2": {
                            "type": "string",
                            "description": "Name of second component",
                        },
                        "angle": {
                            "type": "number",
                            "description": "Angle in degrees",
                        },
                    },
                    "required": ["component1", "component2", "angle"],
                },
            },
            {
                "name": "catia_move_component",
                "description": (
                    "Move a component by translation and/or rotation. "
                    "Translation in mm, rotation in degrees."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component_name": {
                            "type": "string",
                            "description": "Name of the component to move",
                        },
                        "tx": {"type": "number", "description": "Translation X (mm)", "default": 0},
                        "ty": {"type": "number", "description": "Translation Y (mm)", "default": 0},
                        "tz": {"type": "number", "description": "Translation Z (mm)", "default": 0},
                        "rx": {"type": "number", "description": "Rotation around X (degrees)", "default": 0},
                        "ry": {"type": "number", "description": "Rotation around Y (degrees)", "default": 0},
                        "rz": {"type": "number", "description": "Rotation around Z (degrees)", "default": 0},
                    },
                    "required": ["component_name"],
                },
            },
            {
                "name": "catia_list_components",
                "description": "List all components in the active assembly/product with their names and positions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "catia_list_constraints",
                "description": "List all assembly constraints in the active product.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        match tool_name:
            case "catia_add_component":
                return self._add_component(arguments["file_path"])
            case "catia_add_new_part":
                return self._add_new_part(arguments.get("name"))
            case "catia_fix_constraint":
                return self._fix_constraint(arguments["component_name"])
            case "catia_coincidence_constraint":
                return self._coincidence_constraint(arguments)
            case "catia_offset_constraint":
                return self._offset_constraint(arguments)
            case "catia_angle_constraint":
                return self._angle_constraint(arguments)
            case "catia_move_component":
                return self._move_component(arguments)
            case "catia_list_components":
                return self._list_components()
            case "catia_list_constraints":
                return self._list_constraints()
            case _:
                raise ValueError(f"Unknown assembly tool: {tool_name}")

    def _add_component(self, file_path: str) -> str:
        product = self.conn.get_active_product()
        source = Path(file_path)
        if not source.is_file() or source.suffix.lower() not in {".catpart", ".catproduct"}:
            raise FileNotFoundError(
                f"No accessible CATPart/CATProduct file at {file_path!r} on this Windows computer"
            )
        products = product.Products
        previous_count = products.Count
        products.AddComponentsFromFiles([str(source.resolve())], "All")
        if products.Count != previous_count + 1:
            raise RuntimeError(
                f"CATIA returned from AddComponentsFromFiles, but Products.Count changed "
                f"from {previous_count} to {products.Count}, not by one. Inspect the assembly "
                "before retrying; the component may be missing or insertion partial."
            )
        component = products.Item(products.Count)
        try:
            product.Update()
        except Exception as exc:
            raise RuntimeError(
                f"Component {component.Name!r} was inserted but assembly update failed: {exc}. "
                "Inspect the assembly before retrying."
            ) from exc
        try:
            actual_path = str(component.ReferenceProduct.Parent.FullName)
        except Exception as exc:
            raise RuntimeError(
                f"Component {component.Name!r} was inserted but its source document "
                f"could not be verified: {exc}. Inspect the assembly before retrying."
            ) from exc
        if ntpath.normcase(ntpath.normpath(actual_path)) != ntpath.normcase(
            ntpath.normpath(str(source.resolve()))
        ):
            raise RuntimeError(
                f"Component {component.Name!r} was inserted, but CATIA reports source "
                f"{actual_path!r}, expected {str(source.resolve())!r}."
            )
        self.conn.refresh_display()
        return (f"Component added: instance={component.Name!r}, "
                f"part_number={component.PartNumber!r}, source={actual_path!r}")

    def _add_new_part(self, name: str | None = None) -> str:
        product = self.conn.get_active_product()
        products = product.Products
        previous_count = products.Count
        new_product = products.AddNewComponent("Part", name or "NewPart")
        if products.Count != previous_count + 1:
            raise RuntimeError(
                "CATIA returned from AddNewComponent, but the assembly component count "
                "did not increase by exactly one. Inspect the assembly before retrying."
            )
        actual_part_number = str(new_product.PartNumber)
        if name and actual_part_number != name:
            raise RuntimeError(
                f"Part component was created, but PartNumber is {actual_part_number!r} "
                f"instead of {name!r}. Inspect it before retrying."
            )
        try:
            new_product.ReferenceProduct.Parent.Part
        except Exception as exc:
            raise RuntimeError(
                f"Product {new_product.Name!r} was created but the referenced CATPart "
                f"could not be verified: {exc}. Inspect before retrying."
            ) from exc
        product.Update()
        self.conn.refresh_display()
        return (f"New unsaved CATPart component created: instance={new_product.Name!r}, "
                f"part_number={actual_part_number!r}")

    def _selected_assembly_references(self, expected_count: int,
                                      component_names: list[str], *,
                                      require_component: bool = False) -> list[Any]:
        document = self.conn.active_document
        product = self.conn.get_active_product()
        selection = document.Selection
        if selection.Count2 != expected_count:
            raise ValueError(
                f"Select exactly {expected_count} assembly instance support(s) in CATIA "
                "before creating a constraint"
            )
        references = []
        for position, expected_name in enumerate(component_names, start=1):
            selected = selection.Item2(position)
            selected_type = str(selected.Type)
            is_product = selected_type.lower() == "product"
            if require_component and not is_product:
                raise ValueError(
                    f"Selection {position} is {selected_type!r}, not a component Product"
                )
            if not require_component and is_product:
                raise ValueError(
                    f"Selection {position} is a whole Product; select its exact geometric support"
                )
            try:
                # For Fix, Value is the explicitly selected Product itself.
                # For geometric supports, LeafProduct identifies its instance.
                leaf_name = str(
                    selected.Value.Name if require_component else selected.LeafProduct.Name
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Cannot verify assembly instance for selection {position}: {exc}"
                ) from exc
            if leaf_name != expected_name:
                raise ValueError(
                    f"Selection {position} belongs to instance {leaf_name!r}, "
                    f"expected {expected_name!r}"
                )
            try:
                reference = selected.Reference
                if reference is None:
                    raise ValueError("CATIA returned an empty Reference")
                references.append(reference)
            except Exception as exc:
                raise RuntimeError(
                    f"Selection {position} has no exact assembly Reference: {exc}"
                ) from exc
        return references

    def _fix_constraint(self, component_name: str) -> str:
        product = self.conn.get_active_product()
        constraints = product.Connections("CATIAConstraints")
        reference = self._selected_assembly_references(
            1, [component_name], require_component=True)[0]
        cst = constraints.AddMonoEltCst(0, reference)  # catCstTypeReference
        cst.Name = f"Fix.{component_name}"
        product.Update()
        self.conn.refresh_display()
        return (f"Fix constraint {cst.Name!r} created for selected instance "
                f"{component_name!r}; status={getattr(cst, 'Status', 'unavailable')!r}. "
                "Verify instance pose and solved status in CATIA.")

    def _coincidence_constraint(self, args: dict[str, Any]) -> str:
        if args.get("element1") is not None or args.get("element2") is not None:
            raise ValueError(
                "element1/element2 names are not exact support references. "
                "Select both supports in CATIA and omit these arguments."
            )
        product = self.conn.get_active_product()
        constraints = product.Connections("CATIAConstraints")

        refs = self._selected_assembly_references(
            2, [args["component1"], args["component2"]])
        cst = constraints.AddBiEltCst(2, *refs)  # catCstTypeOn
        product.Update()
        self.conn.refresh_display()
        return (
            f"Coincidence constraint created between the two selected supports; "
            f"status={getattr(cst, 'Status', 'unavailable')!r}. "
            "Verify supported geometry and orientation in CATIA."
        )

    def _offset_constraint(self, args: dict[str, Any]) -> str:
        product = self.conn.get_active_product()
        constraints = product.Connections("CATIAConstraints")

        offset = args["offset"]
        if not isinstance(offset, (int, float)) or not math.isfinite(offset) or offset < 0:
            raise ValueError("Offset must be a finite nonnegative distance")
        refs = self._selected_assembly_references(
            2, [args["component1"], args["component2"]])
        cst = constraints.AddBiEltCst(1, *refs)  # catCstTypeDistance
        cst.Dimension.Value = args["offset"]
        product.Update()
        if not math.isclose(float(cst.Dimension.Value), offset, abs_tol=1e-7):
            raise RuntimeError("Offset constraint was created, but dimension readback differs")
        self.conn.refresh_display()
        return (
            f"Offset constraint created between selected supports; dimension={offset} "
            f"(CATIA units). Verify physical gap and orientation in CATIA."
        )

    def _angle_constraint(self, args: dict[str, Any]) -> str:
        product = self.conn.get_active_product()
        constraints = product.Connections("CATIAConstraints")

        angle = args["angle"]
        if not isinstance(angle, (int, float)) or not math.isfinite(angle) or not 0 <= angle <= 180:
            raise ValueError("Assembly angle must be finite and between 0 and 180 degrees")
        refs = self._selected_assembly_references(
            2, [args["component1"], args["component2"]])
        cst = constraints.AddBiEltCst(6, *refs)  # catCstTypeAngle
        cst.Dimension.Value = args["angle"]
        product.Update()
        if not math.isclose(float(cst.Dimension.Value), angle, abs_tol=1e-7):
            raise RuntimeError("Angle constraint was created, but dimension readback differs")
        self.conn.refresh_display()
        return (
            f"Angle constraint created between selected supports; dimension={angle}°. "
            "Verify orientation and solver status in CATIA."
        )

    def _move_component(self, args: dict[str, Any]) -> str:
        product = self.conn.get_active_product()
        products = product.Products
        component_name = args["component_name"]
        matches = [products.Item(index) for index in range(1, products.Count + 1)
                   if str(products.Item(index).Name) == component_name]
        if len(matches) != 1:
            raise ValueError(
                f"Component instance name {component_name!r} matched {len(matches)} "
                "instances. Use a unique instance name before moving anything."
            )
        component = matches[0]
        values = [args.get(key, 0) for key in ("tx", "ty", "tz", "rx", "ry", "rz")]
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) for value in values):
            raise ValueError("Translation and rotation increments must be finite numbers")
        position = component.Position
        output = [0.0] * 12
        returned = position.GetComponents(output)
        old = list(returned) if isinstance(returned, (list, tuple)) and len(returned) == 12 else output
        if len(old) != 12 or any(not math.isfinite(float(value)) for value in old):
            raise RuntimeError("CATIA did not return a valid 12-component Position")
        # Position stores local X, Y, Z axes as columns, followed by translation.
        old_rotation = [[old[col * 3 + row] for col in range(3)] for row in range(3)]
        for first in range(3):
            for second in range(3):
                dot = sum(old_rotation[row][first] * old_rotation[row][second]
                          for row in range(3))
                if not math.isclose(dot, float(first == second), abs_tol=1e-5):
                    raise RuntimeError("CATIA returned a non-orthonormal component pose")
        determinant = (
            old_rotation[0][0] * (old_rotation[1][1] * old_rotation[2][2] - old_rotation[1][2] * old_rotation[2][1])
            - old_rotation[0][1] * (old_rotation[1][0] * old_rotation[2][2] - old_rotation[1][2] * old_rotation[2][0])
            + old_rotation[0][2] * (old_rotation[1][0] * old_rotation[2][1] - old_rotation[1][1] * old_rotation[2][0])
        )
        if not math.isclose(determinant, 1.0, abs_tol=1e-5):
            raise RuntimeError("CATIA returned an invalid or mirrored component pose")

        rx, ry, rz = (math.radians(value) for value in values[3:])
        cx, sx = math.cos(rx), math.sin(rx)
        cy, sy = math.cos(ry), math.sin(ry)
        cz, sz = math.cos(rz), math.sin(rz)
        delta = [
            [cy * cz, cz * sx * sy - cx * sz, sx * sz + cx * cz * sy],
            [cy * sz, cx * cz + sx * sy * sz, cx * sy * sz - cz * sx],
            [-sy, cy * sx, cx * cy],
        ]
        rotation = [[sum(delta[row][k] * old_rotation[k][col] for k in range(3))
                     for col in range(3)] for row in range(3)]
        target = [rotation[row][col] for col in range(3) for row in range(3)]
        target.extend(old[9 + index] + values[index] for index in range(3))
        position.SetComponents(target)
        product.Update()
        actual = [0.0] * 12
        returned = position.GetComponents(actual)
        actual = list(returned) if isinstance(returned, (list, tuple)) and len(returned) == 12 else actual
        if any(not math.isclose(float(actual[i]), target[i], abs_tol=1e-4)
               for i in range(12)):
            raise RuntimeError(
                "SetComponents returned, but the solved assembly pose differs from the "
                "requested pose. The component may be constrained; inspect before retrying."
            )
        self.conn.refresh_display()

        return (
            f"Component {args['component_name']!r} pose increment applied and read back: "
            f"translation in parent axes={values[:3]} mm; rotation about component origin "
            f"using parent axes Rz*Ry*Rx={values[3:]} degrees."
        )

    def _list_components(self) -> str:
        product = self.conn.get_active_product()
        products = product.Products

        components = []
        for i in range(1, products.Count + 1):
            comp = products.Item(i)
            pos = comp.Position
            matrix = [0.0] * 12
            try:
                pos.GetComponents(matrix)
            except Exception:
                pass
            components.append({
                "index": i,
                "name": comp.Name,
                "part_number": comp.PartNumber,
                "position": {
                    "x": round(matrix[9], 3),
                    "y": round(matrix[10], 3),
                    "z": round(matrix[11], 3),
                },
            })

        if not components:
            return "No components in the active assembly"
        return json.dumps(components, indent=2, ensure_ascii=False)

    def _list_constraints(self) -> str:
        product = self.conn.get_active_product()
        constraints = product.Connections("CATIAConstraints")

        cst_list = []
        for i in range(1, constraints.Count + 1):
            cst = constraints.Item(i)
            info = {
                "index": i,
                "name": cst.Name,
                "type": cst.Type if hasattr(cst, "Type") else "unknown",
            }
            try:
                info["status"] = "resolved" if cst.Status == 0 else "broken"
            except Exception:
                pass
            cst_list.append(info)

        if not cst_list:
            return "No constraints in the active assembly"
        return json.dumps(cst_list, indent=2, ensure_ascii=False)
