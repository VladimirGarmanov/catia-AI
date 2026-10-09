"""Restricted 2D composites. Explicit copies, no hidden deletion or GUI equivalence."""
import math

from catia_mcp.com_arrays import read_array
from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.engineering import HANDLE, NUMBER, POSITIVE, dimension
from catia_mcp.tools.operations import OperationTools, BOOL, array, group

XY = array(NUMBER, 2, 2)


class SketchOperationTools(OperationTools):
    def get_tool_definitions(self):
        return [
            group("catia_sketch_profile", "Create shared-endpoint polyline in OPEN sketch coordinates (mm). Optional closed loop; not a fully constrained profile. Existing primitives remain unchanged.",
                  {"polyline": {"points_mm": array(XY, 2), "closed": BOOL}}),
            group("catia_sketch_transform", "Create non-associative transformed copies of lines/full circles in current sketch. No splines/arcs, no implicit deletion or constraint copying. Axis/center are sketch-local mm.", {
                "translate": {"offset_mm": XY},
                "rotate": {"center_mm": XY, "angle_deg": NUMBER},
                "scale": {"center_mm": XY, "factor": POSITIVE},
                "mirror": {"axis_start_mm": XY, "axis_end_mm": XY},
                "point_symmetry": {"center_mm": XY},
                "offset": {"distance_mm": NUMBER},
            }, {"handles": array(HANDLE)}),
            group("catia_sketch_line_edit", "Restricted geometric replacement of unconstrained lines. Original lines become construction ONLY with explicit flag; never deleted. New entities are not associative GUI Trim/Corner features. Shared endpoints/constraints require manual design review.", {
                "trim_interval": {"line_handle": HANDLE, "start_fraction": {"type": "number", "minimum": 0, "maximum": 1}, "end_fraction": {"type": "number", "minimum": 0, "maximum": 1}},
                "break": {"line_handle": HANDLE, "fraction": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1}},
                "chamfer": {"first_line_handle": HANDLE, "second_line_handle": HANDLE, "distance_mm": POSITIVE},
                "corner": {"first_line_handle": HANDLE, "second_line_handle": HANDLE, "radius_mm": POSITIVE},
            }, {"make_sources_construction": {"const": True}}),
            group("catia_sketch_relation", "Parametric diameter through R=D/2, or equality between existing dimensional parameters. Does not promise a GUI diameter glyph. No guessed diameter enum.", {
                "diameter": {"circle_handle": HANDLE, "diameter_mm": POSITIVE, "parameter_name": HANDLE},
                "equal_parameters": {"source_parameter_handle": HANDLE, "target_parameter_handle": HANDLE, "formula_name": HANDLE},
            }),
        ]

    def context(self):
        sketcher = self.engineering.sketcher
        sketcher._ensure_sketch_open()
        return sketcher._active_sketch, sketcher._active_factory

    def geometry(self, handle, kinds):
        sketch, _ = self.context()
        obj = self.obj(handle, kinds)
        if not any(same_object(obj, sketch.GeometricElements.Item(i)) for i in range(1, sketch.GeometricElements.Count + 1)):
            raise CADOperationError("INVALID_ARGUMENT", "Geometry belongs to another sketch")
        return obj

    def endpoints(self, line):
        values = read_array(line.GetEndPoints, 4)
        return values[:2], values[2:]

    def add_line(self, factory, p, q):
        if math.dist(p, q) < 1e-9:
            raise CADOperationError("INVALID_ARGUMENT", "Zero-length line")
        obj = factory.CreateLine(*p, *q)
        self.state.mark_created(obj, "line2d")
        return obj

    def finish_sketch(self, sketch):
        sketch.Evaluate()
        statuses = [int(sketch.Constraints.Item(i).Status) for i in range(1, sketch.Constraints.Count + 1)]
        if any(status != 0 for status in statuses):
            raise CADOperationError("POSTCONDITION_FAILED", f"Sketch constraint statuses: {statuses}")
        return {"ok": True, "constraint_statuses": statuses, "edition_open": True,
                "warning": "Close sketch and Update before accepting geometry; unconstrained DOF are not inferred"}

    def execute(self, name, a):
        sketch, factory = self.context()
        if name == "catia_sketch_profile":
            points = a["points_mm"]
            if a["closed"] and len(points) < 3:
                raise CADOperationError("INVALID_ARGUMENT", "Closed profile needs at least three vertices")
            pairs = list(zip(points, points[1:] + ([points[0]] if a["closed"] else [])))
            if any(math.dist(p, q) < 1e-9 for p, q in pairs):
                raise CADOperationError("INVALID_ARGUMENT", "Repeated adjacent profile point")
            vertices = [factory.CreatePoint(*p) for p in points]
            for vertex in vertices:
                self.state.mark_created(vertex, "point2d")
            for i, (p, q) in enumerate(pairs):
                line = self.add_line(factory, p, q)
                line.StartPoint, line.EndPoint = vertices[i], vertices[(i + 1) % len(vertices)]
        elif name == "catia_sketch_transform":
            self.transform(a, factory)
        elif name == "catia_sketch_line_edit":
            self.line_edit(a, sketch, factory)
        else:
            self.relation(a, sketch)
        return self.finish_sketch(sketch)

    def transform(self, a, factory):
        mode = a["mode"]
        if mode == "mirror" and math.dist(a["axis_start_mm"], a["axis_end_mm"]) < 1e-9:
            raise CADOperationError("INVALID_ARGUMENT", "Mirror axis has zero length")
        def point(p):
            if mode == "translate":
                return [p[i] + a["offset_mm"][i] for i in range(2)]
            if mode == "mirror":
                origin = a["axis_start_mm"]
                d = [a["axis_end_mm"][i] - origin[i] for i in range(2)]
                t = sum((p[i] - origin[i]) * d[i] for i in range(2)) / sum(v*v for v in d)
                return [2 * (origin[i] + t * d[i]) - p[i] for i in range(2)]
            c = a["center_mm"]
            q = [p[i] - c[i] for i in range(2)]
            if mode == "rotate":
                angle = math.radians(a["angle_deg"])
                return [c[0] + q[0]*math.cos(angle) - q[1]*math.sin(angle), c[1] + q[0]*math.sin(angle) + q[1]*math.cos(angle)]
            factor = -1 if mode == "point_symmetry" else a["factor"]
            return [c[i] + factor*q[i] for i in range(2)]
        plans = []
        for h in a["handles"]:
            obj = self.geometry(h, {"line2d", "circle2d"})
            if self.state.resolve(h).kind == "line2d":
                p, q = self.endpoints(obj)
                if mode == "offset":
                    length = math.dist(p, q)
                    if length < 1e-9:
                        raise CADOperationError("INVALID_ARGUMENT", "Degenerate line")
                    offset = [-(q[1]-p[1])*a["distance_mm"]/length, (q[0]-p[0])*a["distance_mm"]/length]
                    plans.append(("line", [p[i]+offset[i] for i in range(2)], [q[i]+offset[i] for i in range(2)]))
                else:
                    plans.append(("line", point(p), point(q)))
            else:
                extents = read_array(obj.GetParamExtents, 2)
                if not obj.IsPeriodic() or abs(abs(extents[1] - extents[0]) - 2*math.pi) > 1e-7:
                    raise CADOperationError("UNSUPPORTED_OPERATION", "Only full circles, not arcs, are supported")
                c, r = read_array(obj.GetCenter, 2), float(obj.Radius)
                new_radius = r + a["distance_mm"] if mode == "offset" else r * (a["factor"] if mode == "scale" else 1)
                if new_radius <= 0:
                    raise CADOperationError("INVALID_ARGUMENT", "Offset collapses circle radius")
                plans.append(("circle", c if mode == "offset" else point(c), new_radius))
        for kind, p, q in plans:
            if kind == "line":
                self.add_line(factory, p, q)
            else:
                self.state.mark_created(factory.CreateClosedCircle(*p, q), "circle2d")

    def line_edit(self, a, sketch, factory):
        # Constraint dependency reconstruction is not implemented. Refuse rather than destroy intent.
        if sketch.Constraints.Count:
            raise CADOperationError("UNSUPPORTED_OPERATION", "Line editing currently requires a sketch without constraints")
        keys = ["line_handle"] if "line_handle" in a else ["first_line_handle", "second_line_handle"]
        lines = [self.geometry(a[key], {"line2d"}) for key in keys]
        endpoints = [self.endpoints(line) for line in lines]
        plans, arc = [], None
        if a["mode"] in {"trim_interval", "break"}:
            p, q = endpoints[0]
            at = lambda t: [p[i] + t * (q[i] - p[i]) for i in range(2)]
            if a["mode"] == "break":
                plans = [(p, at(a["fraction"])), (at(a["fraction"]), q)]
            else:
                if a["start_fraction"] >= a["end_fraction"]:
                    raise CADOperationError("INVALID_ARGUMENT", "Trim fractions must increase")
                plans = [(at(a["start_fraction"]), at(a["end_fraction"]))]
        else:
            (p, vertex), (other_vertex, q) = endpoints
            if math.dist(vertex, other_vertex) > 1e-7:
                raise CADOperationError("UNSUPPORTED_OPERATION", "Corner requires first line end = second line start")
            lp, lq = math.dist(p, vertex), math.dist(q, vertex)
            if min(lp, lq) < 1e-9:
                raise CADOperationError("INVALID_ARGUMENT", "Degenerate corner line")
            u, v = [(p[i]-vertex[i])/lp for i in range(2)], [(q[i]-vertex[i])/lq for i in range(2)]
            angle = math.acos(max(-1, min(1, sum(u[i]*v[i] for i in range(2)))))
            if min(angle, math.pi-angle) < 1e-7:
                raise CADOperationError("INVALID_ARGUMENT", "Corner lines are collinear")
            distance = a["distance_mm"] if a["mode"] == "chamfer" else a["radius_mm"] / math.tan(angle/2)
            if distance >= min(lp, lq):
                raise CADOperationError("INVALID_ARGUMENT", "Corner consumes an entire source segment")
            t1, t2 = [[vertex[i]+distance*d[i] for i in range(2)] for d in (u, v)]
            plans = [(p, t1), (t2, q)]
            if a["mode"] == "chamfer":
                plans.append((t1, t2))
            else:
                bisector_length = math.sqrt(sum((u[i]+v[i])**2 for i in range(2)))
                center = [vertex[i] + (u[i]+v[i])/bisector_length * a["radius_mm"]/math.sin(angle/2) for i in range(2)]
                start, end = [math.atan2(t[1]-center[1], t[0]-center[0]) for t in (t1, t2)]
                if (end-start) % (2*math.pi) > math.pi:
                    start, end = end, start
                arc = (*center, a["radius_mm"], start, start + (end-start) % (2*math.pi))
        for p, q in plans:
            self.add_line(factory, p, q)
        if arc is not None:
            self.state.mark_created(factory.CreateCircle(*arc), "circle2d")
        for key, line in zip(keys, lines):
            self.changed(a[key])
            line.Construction = True

    def relation(self, a, sketch):
        part = self.conn.get_active_part()
        if a["mode"] == "equal_parameters":
            source = self.obj(a["source_parameter_handle"], {"parameter"})
            target = self.obj(a["target_parameter_handle"], {"parameter"})
            if same_object(source, target):
                raise CADOperationError("INVALID_ARGUMENT", "Self-dependent formula is invalid")
            expression = part.Parameters.GetNameToUseInRelation(source)
            relation = part.Relations.CreateFormula(a["formula_name"], "", target, expression)
        else:
            circle = self.geometry(a["circle_handle"], {"circle2d"})
            parameter = part.Parameters.CreateDimension(a["parameter_name"], "LENGTH", 0)
            self.state.mark_created(parameter, "parameter")
            dimension(parameter, a["diameter_mm"], "mm")
            constraint = sketch.Constraints.AddMonoEltCst(14, part.CreateReferenceFromObject(circle))
            self.state.mark_created(constraint, "constraint")
            constraint.Mode = 0
            dimension(constraint.Dimension, a["diameter_mm"] / 2, "mm")
            expression = part.Parameters.GetNameToUseInRelation(parameter) + "/2"
            relation = part.Relations.CreateFormula(a["parameter_name"] + "_radius", "", constraint.Dimension, expression)
        self.state.mark_created(relation, "relation")
