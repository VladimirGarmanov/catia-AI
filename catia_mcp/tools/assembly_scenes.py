"""DMU Product-Scenes for exploded views that leave real occurrence poses untouched.

Only the cached CAA V5 OSMInterfaces contract is used: Product.GetTechnologicalObject
("ProductScenes"), ProductScenes.AddProductSceneFull/AddProductScenePartial/Item/
Remove, ProductScene.Type/ExistsInScene/GetSceneProductData and
SceneProductData.Position Get/SetComponents. No documented call applies a scene
to the product, so none is offered. COM failures are CAPABILITY_UNAVAILABLE; there
is never a fallback to moving Product.Position. ProductScene.Name is not listed on its
cached page (only Type); it is assumed inherited from AnyObject, as ProductScenes.Item
accepts the scene name. Handle resolution reads Name, so this assumption is part of the
Windows validation that is still pending.
"""
from catia_mcp.com_arrays import read_array
from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.assembly_workflow import AssemblyWorkflowTools, HANDLES, POSE, record_schema
from catia_mcp.tools.domain_support import members, member_index, read_properties, verify_equal
from catia_mcp.tools.engineering import HANDLE, NUMBER, tool
from catia_mcp.tools.operations import VECTOR, array, group, unit_vector


READ_TOOLS = frozenset({"catia_assembly_scene_inspect"})
SCENE_NAME = {"type": "string", "minLength": 1, "maxLength": 128}
SCENE_TYPES = {0: "partial", 1: "full"}  # CatSceneType: CatSceneTypeDelta, CatSceneTypeFull.
FRAME = ("scene SceneProductData.Position of an immediate occurrence; axes as columns, "
         "origin mm, assumed parent frame like Product.Position (Windows validation pending)")


def _unavailable(action, exc):
    return CADOperationError("CAPABILITY_UNAVAILABLE",
                             f"{action} failed; DMU scene API/license may be unavailable: {exc}")


class AssemblySceneTools(AssemblyWorkflowTools):
    def get_tool_definitions(self):
        return [
            tool("catia_assembly_scene_inspect", "List Product-Scenes of the active CATProduct (index, handle, name, full/partial type). With scene_handle and component_handles also read real and scene poses; occurrences without scene overload report scene pose null. Never creates scene data, activates or Updates.",
                 {"scene_handle": HANDLE, "component_handles": HANDLES}, readonly=True),
            group("catia_assembly_scene", "Write DMU Product-Scenes for exploded views. Scene poses never move real occurrences; use this instead of catia_assembly_explode for presentation. Poses are 12 values, axes as columns then origin mm. explode_linear moves the k-th listed occurrence by k*spacing_mm along direction from its real pose; explode_offsets uses explicit vectors. Every write reads scene poses back and verifies real poses unchanged. No apply-to-product (not documented), Update, save or rollback. Windows validation pending.", {
                "create": {"name": SCENE_NAME, "scene_type": {"enum": ["full", "partial"]}},
                "set_component_positions": {"scene_handle": HANDLE, "positions": array(
                    record_schema({"component_handle": HANDLE, "axis_components": POSE}), 1, 100)},
                "explode_linear": {"scene_handle": HANDLE, "component_handles": HANDLES,
                                   "direction": VECTOR, "spacing_mm": {**NUMBER, "exclusiveMinimum": 0}},
                "explode_offsets": {"scene_handle": HANDLE, "offsets": array(
                    record_schema({"component_handle": HANDLE, "translation_mm": VECTOR}), 1, 100)},
                "remove": {"scene_handle": HANDLE, "expected_name": SCENE_NAME},
            }),
        ]

    def execute(self, name, args):
        if name not in READ_TOOLS and self.engineering.sketcher._active_sketch is not None:
            raise CADOperationError("SKETCH_OPEN", "Close the edited sketch before assembly scene writes")
        if name == "catia_assembly_scene_inspect":
            return self.inspect_scenes(args)
        return getattr(self, "_scene_" + args["mode"])(args)

    def _scenes(self, root=None):
        root = root if root is not None else self.product()
        try:
            collection = root.GetTechnologicalObject("ProductScenes")
            count = int(collection.Count)
        except Exception as exc:
            raise _unavailable("GetTechnologicalObject('ProductScenes')", exc) from exc
        if count > 500:
            raise CADOperationError("CAPABILITY_UNAVAILABLE", "More than 500 scenes; inspect them in CATIA")
        return collection

    def _scene(self, handle, collection):
        scene = self.obj(handle, {"product_scene"})
        return scene, member_index(collection, scene)

    def _row(self, index, scene):
        data = read_properties(scene, {"Name": str, "Type": int})
        return {"index": index, "handle": self.state.register(scene, "product_scene"),
                "name": data["Name"], "type": SCENE_TYPES.get(data["Type"], "unknown"),
                "native_type": data["Type"], **({"unavailable": data["unavailable"]} if "unavailable" in data else {})}

    def _scene_pose(self, scene, obj):
        try:
            exists = bool(scene.ExistsInScene(obj))
        except Exception as exc:
            raise _unavailable("ProductScene.ExistsInScene", exc) from exc
        if not exists:
            return False, None
        try:
            position = scene.GetSceneProductData(obj).Position
        except Exception as exc:
            raise _unavailable("ProductScene.GetSceneProductData", exc) from exc
        return True, read_array(position.GetComponents, 12)

    def inspect_scenes(self, a):
        collection = self._scenes()
        rows = [self._row(i, scene) for i, scene in members(collection)]
        result = {"ok": True, "scenes": rows, "count": len(rows), "apply_to_product": "not documented; not offered",
                  "warning": "Scene poses are presentation states; real occurrence poses are unchanged"}
        if "component_handles" in a and "scene_handle" not in a:
            raise CADOperationError("INVALID_ARGUMENT", "component_handles requires scene_handle")
        if "scene_handle" in a:
            scene, _ = self._scene(a["scene_handle"], collection)
            positions = []
            targets = self._targets(a["component_handles"]) if a.get("component_handles") else []
            for handle, obj, pose in targets:
                exists, scene_pose = self._scene_pose(scene, obj)
                positions.append({"component_handle": handle, "real_axis_components": pose,
                                  "exists_in_scene": exists, "scene_axis_components": scene_pose})
            result.update(scene_handle=a["scene_handle"], positions=positions, position_frame=FRAME)
        return result

    def _scene_create(self, a):
        name = a["name"]
        if not name.strip() or any(ord(c) < 32 for c in name):
            raise CADOperationError("INVALID_ARGUMENT", "Scene name must be nonblank without control characters")
        document = self._bound_document()
        root = document.Product
        collection = self._scenes(root)
        before = [scene for _, scene in members(collection)]
        if any(str(scene.Name) == name for scene in before):
            raise CADOperationError("INVALID_ARGUMENT", "A scene with this name already exists")
        method = "AddProductSceneFull" if a["scene_type"] == "full" else "AddProductScenePartial"
        self.state.mutation_started = True
        try:
            # CAA example passes the reference root product as iReferenceProducts.
            scene = getattr(collection, method)(name, root)
        except Exception as exc:
            raise _unavailable(f"ProductScenes.{method}", exc) from exc
        finally:
            self._active(document)
            try:  # record anything left behind; must never mask the primary error
                for _, value in members(collection):
                    if not any(same_object(value, old) for old in before):
                        self.state.mark_created(value, "product_scene")
            except Exception:
                pass
        handle = self.state.mark_created(scene, "product_scene")
        try:
            count, actual_name, actual_type = int(collection.Count), str(scene.Name), int(scene.Type)
        except Exception as exc:
            raise CADOperationError("POSTCONDITION_FAILED", f"Scene {handle} created, but readback failed: {exc}") from exc
        verify_equal(count, len(before)+1, "Scene count")
        index = member_index(collection, scene)
        verify_equal(actual_name, name, "Scene name")
        verify_equal(SCENE_TYPES.get(actual_type, "unknown"), a["scene_type"], "Scene type")
        return {"ok": True, "scene_handle": handle, "index": index, "name": name,
                "scene_type": a["scene_type"], "method": method, "real_positions_changed": False,
                "verification": "Native count/name/type readback; Windows validation pending"}

    def _write(self, a, targets, poses):
        for pose in poses:
            self.validate_pose(pose)
        document = self._bound_document()
        root = document.Product
        scene, _ = self._scene(a["scene_handle"], self._scenes(root))
        before = [self._scene_pose(scene, obj)[1] for _, obj, _ in targets]
        # Snapshot EVERY immediate occurrence: the invariant is that no real pose moves.
        occurrences = [obj for _, obj in members(root.Products)]
        real_before = [self._pose(obj) for obj in occurrences]
        self.changed(a["scene_handle"])
        written = []
        for (handle, obj, _), pose in zip(targets, poses):
            self._active(document)
            try:
                position = scene.GetSceneProductData(obj).Position
                position.SetComponents(tuple(pose))
            except Exception as exc:
                raise CADOperationError("CAPABILITY_UNAVAILABLE",
                    f"Scene position write failed for {handle} after {len(written)} written; inspect the scene: {exc}") from exc
            written.append(handle)
        self._active(document)
        try:
            moved = [str(obj.Name) for obj, old in zip(occurrences, real_before)
                     if any(abs(x-y) > 1e-7 for x, y in zip(self._pose(obj), old))]
        except Exception as exc:
            raise CADOperationError("POSTCONDITION_FAILED", f"Scene written; real-pose readback failed: {exc}") from exc
        if moved:  # checked for all occurrences before any scene-pose verdict
            raise CADOperationError("POSTCONDITION_FAILED", f"Scene write changed real poses of {moved}; inspect and restore explicitly")
        rows, mismatches = [], []
        for (handle, obj, real), pose, old in zip(targets, poses, before):
            member_index(root.Products, obj)
            try:
                actual = read_array(scene.GetSceneProductData(obj).Position.GetComponents, 12)
            except CADOperationError:
                raise
            except Exception as exc:
                raise CADOperationError("POSTCONDITION_FAILED", f"Scene pose of {handle} written; readback failed: {exc}") from exc
            if any(abs(x - y) > 1e-7 for x, y in zip(actual, pose)):
                mismatches.append(handle)
            rows.append({"component_handle": handle, "scene_axis_components": actual,
                         "previous_scene_axis_components": old, "real_axis_components": real})
        if mismatches:
            raise CADOperationError("POSTCONDITION_FAILED", f"Scene pose readback differs for {mismatches}; real poses unchanged")
        return {"ok": True, "scene_handle": a["scene_handle"], "positions": rows, "position_frame": FRAME,
                "real_positions_changed": False, "product_updated": False,
                "verification": "Scene readback and unchanged real poses verified; display needs Windows validation"}

    def _scene_set_component_positions(self, a):
        targets = self._targets([row["component_handle"] for row in a["positions"]])
        return self._write(a, targets, [row["axis_components"] for row in a["positions"]])

    def _scene_explode_offsets(self, a):
        targets = self._targets([row["component_handle"] for row in a["offsets"]])
        poses = [p[:9]+[p[9+i]+row["translation_mm"][i] for i in range(3)]
                 for (_, _, p), row in zip(targets, a["offsets"])]
        return self._write(a, targets, poses)

    def _scene_explode_linear(self, a):
        spacing = a["spacing_mm"]
        if not spacing > 0 or spacing > 1e6:
            raise CADOperationError("INVALID_ARGUMENT", "spacing_mm must be positive and finite")
        u = unit_vector(a["direction"])
        targets = self._targets(a["component_handles"])
        poses = [p[:9]+[p[9+i]+k*spacing*u[i] for i in range(3)]
                 for k, (_, _, p) in enumerate(targets, 1)]
        result = self._write(a, targets, poses)
        result.update(direction_unit=list(u), spacing_mm=spacing,
                      offsets_mm=[[k*spacing*x for x in u] for k in range(1, len(targets)+1)])
        return result

    def _scene_remove(self, a):
        document = self._bound_document()
        collection = self._scenes(document.Product)
        scene, _ = self._scene(a["scene_handle"], collection)
        verify_equal(str(scene.Name), a["expected_name"], "Scene name before remove")
        count = int(collection.Count)
        self.changed(a["scene_handle"])
        try:
            collection.Remove(scene)
        except Exception as exc:
            raise _unavailable("ProductScenes.Remove", exc) from exc
        finally:
            self._active(document)
        verify_equal(int(collection.Count), count-1, "Scene count after remove")
        if any(same_object(scene, value) for _, value in members(collection)):
            raise CADOperationError("POSTCONDITION_FAILED", "Removed scene is still listed")
        self.state.objects.pop(a["scene_handle"], None)
        return {"ok": True, "removed": a["expected_name"], "real_positions_changed": False}
