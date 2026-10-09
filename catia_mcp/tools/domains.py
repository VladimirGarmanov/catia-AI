"""Domain discovery and typed assembly/Knowledgeware operations."""
from pathlib import Path

from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.engineering import HANDLE, NUMBER, POSITIVE, tool, geometry_kind
from catia_mcp.tools.operations import OperationTools, BOOL, INTEGER, array, group


def absolute_file(value, existing=False):
    path = Path(value)
    if not path.is_absolute():
        raise CADOperationError("INVALID_ARGUMENT", "An explicit absolute file path is required")
    if existing and not path.is_file():
        raise CADOperationError("INVALID_ARGUMENT", "Input file does not exist")
    return path


class DomainTools(OperationTools):
    def get_tool_definitions(self):
        return [
            tool("catia_domain_objects", "Read active Product/Drawing/Part relations and all open document IDs. No activation or geometry changes. Handles remain document-bound.",
                 {"max_objects": {"type": "integer", "minimum": 1, "maximum": 5000}}, readonly=True),
            group("catia_assembly_operation", "Explicit Product occurrence operations, metadata, work mode and publication. Does not save or close documents.", {
                "new_product": {"parent_handle": HANDLE, "part_number": HANDLE},
                "add_occurrence": {"parent_handle": HANDLE, "reference_handle": HANDLE},
                "replace_component": {"parent_handle": HANDLE, "component_handle": HANDLE, "file_path": HANDLE, "all_instances": BOOL},
                "metadata": {"product_handle": HANDLE, "part_number": HANDLE, "revision": {"type": "string"}, "definition": {"type": "string"}, "nomenclature": {"type": "string"}},
                "work_mode": {"product_handle": HANDLE, "work_mode": {"enum": ["default", "visualization", "design"]}},
                "publish_selection": {"product_handle": HANDLE, "selection_handle": HANDLE, "name": HANDLE},
                "bom": {"product_handle": HANDLE, "file_path": HANDLE, "format": {"enum": ["text", "html"]}, "allow_overwrite": BOOL},
                "contact": {"first_selection_handle": HANDLE, "second_selection_handle": HANDLE},
                "fix_together": {"product_handles": array(HANDLE, 2)},
            }),
            group("catia_knowledgeware", "Typed relations and design tables in active Part. Rule uses CreateProgram, not CreateRule. CATIA expressions only; no Python/macros.", {
                "rule": {"name": HANDLE, "body": HANDLE},
                "check": {"name": HANDLE, "body": HANDLE},
                "law": {"name": HANDLE, "body": HANDLE},
                "formula_modify": {"relation_handle": HANDLE, "expression": HANDLE},
                "design_table": {"name": HANDLE, "file_path": HANDLE, "copy_data": BOOL,
                                 "associations": array({"type": "object", "properties": {"parameter_handle": HANDLE, "column": HANDLE},
                                                        "required": ["parameter_handle", "column"], "additionalProperties": False}),
                                 "configuration": {"type": "integer", "minimum": 1}},
                "table_configuration": {"table_handle": HANDLE, "configuration": {"type": "integer", "minimum": 1}, "synchronize": BOOL},
            }),
            group("catia_template_instance", "Instantiate an explicitly named local PowerCopy/UDF template in a Body. Finally closes InstanceFactory protocols; no rollback promised. Template must already be trusted by user.", {
                "file_template": {"body_handle": HANDLE, "file_path": HANDLE, "template_name": HANDLE,
                                  "inputs": array({"type": "object", "properties": {"name": HANDLE, "handle": HANDLE},
                                                   "required": ["name", "handle"], "additionalProperties": False}),
                                  "parameters": array({"type": "object", "properties": {"name": HANDLE, "value_with_unit": HANDLE},
                                                        "required": ["name", "value_with_unit"], "additionalProperties": False}, 0)},
                "reference_udf": {"body_handle": HANDLE, "reference_handle": HANDLE},
            }),
            group("catia_visibility", "Show/hide exact whole objects. Requires an initially empty selection and leaves it empty; exact selected subelements cannot be safely restored through Value. No deletion.",
                  {"set": {"handles": array(HANDLE), "visible": BOOL}}),
        ]

    def execute(self, name, a):
        return {"catia_domain_objects": self.discover, "catia_assembly_operation": self.assembly,
                "catia_knowledgeware": self.knowledgeware, "catia_template_instance": self.template,
                "catia_visibility": self.visibility}[name](a)

    def discover(self, a):
        limit, result, warnings = a.get("max_objects", 500), [], []
        def add(value, kind, parent=None):
            if len(result) >= limit:
                return None
            h = self.state.register(value, kind)
            result.append({"handle": h, "kind": kind, "name": str(value.Name), "parent": parent})
            return h
        def visit(collection, kind, parent=None, depth=0):
            if depth > 30:
                warnings.append("Maximum occurrence depth reached")
                return
            for i in range(1, collection.Count + 1):
                value = collection.Item(i)
                h = add(value, kind, parent)
                if h is None:
                    break
                if kind == "product":
                    visit(value.Products, "product", h, depth + 1)
                    visit(value.Publications, "publication", h, depth + 1)
                elif kind == "sheet":
                    visit(value.Views, "view", h, depth + 1)
                elif kind == "view":
                    for attr, child in (("GeometricElements", "drawing_geometry"), ("Dimensions", "drawing_dimension"), ("Texts", "drawing_text")):
                        try:
                            visit(getattr(value, attr), child, h, depth + 1)
                        except Exception as exc:
                            warnings.append(f"{attr}: {exc}")
        doc = self.conn.active_document
        if str(doc.Name).lower().endswith(".catdrawing"):
            visit(doc.Sheets, "sheet")
        elif str(doc.Name).lower().endswith(".catproduct"):
            h = add(doc.Product, "product")
            visit(doc.Product.Products, "product", h)
        else:
            part = self.conn.get_active_part()
            visit(part.Relations, "relation")
            visit(part.AxisSystems, "axis_system")
        docs = self.conn.app.Documents
        sources = [{"document_id": self.state.document_id(docs.Item(i)), "name": str(docs.Item(i).Name)}
                   for i in range(1, docs.Count + 1)]
        return {"ok": True, "objects": result, "open_documents": sources, "warnings": warnings,
                "truncated": len(result) >= limit, "session": self.state.context(self.state.document_id())}

    def product(self):
        doc = self.conn.active_document
        if not str(doc.Name).lower().endswith(".catproduct"):
            raise CADOperationError("WRONG_DOCUMENT_TYPE", "Active document must be a CATProduct")
        return doc.Product

    def assembly(self, a):
        root, mode = self.product(), a["mode"]
        if mode == "fix_together":
            products = [self.obj(h, {"product"}) for h in a["product_handles"]]
            try:
                collection = root.FixTogethers
            except Exception as exc:
                raise CADOperationError("CAPABILITY_UNAVAILABLE", "Product.FixTogethers is not exposed by this COM release; no alternate getter is guessed") from exc
            group_object = collection.Add()
            h = self.state.mark_created(group_object, "fix_together")
            for product in products:
                group_object.AddProduct(product)
            result = self.update(root)
            result.update(handle=h, warning="Collection getter is release-dependent; independent relative-transform verification required")
            return result
        if mode in {"new_product", "add_occurrence", "replace_component"}:
            parent = self.obj(a["parent_handle"], {"product"})
            if mode == "new_product":
                obj = parent.Products.AddNewProduct(a["part_number"])
            elif mode == "add_occurrence":
                source = self.obj(a["reference_handle"], {"product"})
                obj = parent.Products.AddComponent(source.ReferenceProduct)
            else:
                old = self.obj(a["component_handle"], {"product"})
                if not any(same_object(parent.Products.Item(i), old) for i in range(1, parent.Products.Count + 1)):
                    raise CADOperationError("INVALID_ARGUMENT", "Component is not a child of this parent")
                path = absolute_file(a["file_path"], True)
                self.changed(a["component_handle"])
                obj = parent.Products.ReplaceComponent(old, str(path), a["all_instances"])
            handle = self.state.mark_created(obj, "product")
            result = self.update(root)
            result["handle"] = handle
            return result
        if mode == "contact":
            records = [self.state.resolve(a[k]) for k in ("first_selection_handle", "second_selection_handle")]
            if any(r.reference is None for r in records):
                raise CADOperationError("WRONG_GEOMETRY_TYPE", "Contact requires exact current occurrence selections")
            constraint = root.Connections("CATIAConstraints").AddBiEltCst(20, *(r.reference for r in records))
            h = self.state.mark_created(constraint, "constraint")
            result = self.update(root)
            result.update(handle=h, constraint_status=int(constraint.Status))
            if constraint.Status != 0:
                raise CADOperationError("POSTCONDITION_FAILED", "Assembly constraint is not solved")
            return result
        product = self.obj(a["product_handle"], {"product"})
        if mode == "metadata" and not same_object(product, root):
            raise CADOperationError("DOCUMENT_MISMATCH", "Occurrence metadata can modify an external reference document. Only the active root Product metadata is writable here")
        if mode == "bom":
            path = absolute_file(a["file_path"])
            if path.suffix.lower() not in ({".txt"} if a["format"] == "text" else {".htm", ".html"}):
                raise CADOperationError("INVALID_ARGUMENT", "BOM requires .txt or .html output, never a CAD file")
            if path.exists() and not a["allow_overwrite"]:
                raise CADOperationError("INVALID_ARGUMENT", "File exists; overwrite requires explicit opt-in")
            product.ExtractBOM(0 if a["format"] == "text" else 2, str(path))
            if not path.is_file() or not path.stat().st_size:
                raise CADOperationError("POSTCONDITION_FAILED", "BOM output missing or empty")
            return {"ok": True, "path": str(path)}
        self.changed(a["product_handle"])
        if mode == "metadata":
            product.PartNumber = a["part_number"]
            product.Revision, product.Definition, product.Nomenclature = a["revision"], a["definition"], a["nomenclature"]
            result = self.update(root)
            result["readback"] = {k: str(getattr(product, k)) for k in ("PartNumber", "Revision", "Definition", "Nomenclature")}
            return result
        if mode == "work_mode":
            product.ApplyWorkMode({"default": 0, "visualization": 1, "design": 2}[a["work_mode"]])
        else:
            record = self.state.resolve(a["selection_handle"])
            if record.reference is None:
                raise CADOperationError("INVALID_ARGUMENT", "Publication requires an exact current selection Reference")
            publications = product.Publications
            if any(str(publications.Item(i).Name) == a["name"] for i in range(1, publications.Count + 1)):
                raise CADOperationError("INVALID_ARGUMENT", "Publication exists; replacement is not authorized")
            publication = publications.Add(a["name"])
            self.state.mark_created(publication, "publication")
            publications.SetDirect(a["name"], record.reference)
        return self.update(root)

    def knowledgeware(self, a):
        part, mode = self.conn.get_active_part(), a["mode"]
        if mode in {"rule", "check", "law"}:
            constructors = {"rule": "CreateProgram", "check": "CreateCheck", "law": "CreateLaw"}
            obj = getattr(part.Relations, constructors[mode])(a["name"], "Created by typed CATIA MCP", a["body"])
            h = self.state.mark_created(obj, "relation")
        elif mode == "formula_modify":
            obj = self.obj(a["relation_handle"], {"relation"})
            self.changed(a["relation_handle"])
            obj.Modify(a["expression"])
            h = a["relation_handle"]
        elif mode == "design_table":
            path = absolute_file(a["file_path"], True)
            associations = [(self.obj(row["parameter_handle"], {"parameter"}), row["column"]) for row in a["associations"]]
            obj = part.Relations.CreateDesignTable(a["name"], "", a["copy_data"], str(path))
            h = self.state.mark_created(obj, "relation")
            for parameter, column in associations:
                obj.AddAssociation(parameter, column)
            obj.Configuration = a["configuration"]
        else:
            obj = self.obj(a["table_handle"], {"relation"})
            self.changed(a["table_handle"])
            if a["synchronize"]:
                obj.Synchronize()
            obj.Configuration = a["configuration"]
            h = a["table_handle"]
        result = self.update(part)
        result["handle"] = h
        if "configuration" in a:
            result["configuration"] = int(obj.Configuration)
            if result["configuration"] != a["configuration"]:
                raise CADOperationError("POSTCONDITION_FAILED", "Design table configuration differs")
        return result

    def template(self, a):
        part = self.conn.get_active_part()
        if a["mode"] == "reference_udf":
            reference = self.obj(a["reference_handle"], {"feature"})
            self.engineering.body(a["body_handle"])
            obj = part.GetCustomerFactory("InstanceFactory").AddInstance(reference)
            return self.finish(obj)
        path = absolute_file(a["file_path"], True)
        inputs = [(entry["name"], self.state.resolve(entry["handle"]).value) for entry in a["inputs"]]
        self.engineering.body(a["body_handle"])
        factory = part.GetCustomerFactory("InstanceFactory")
        opened = instantiating = False
        self.state.mutation_started = True
        try:
            factory.BeginInstanceFactory(a["template_name"], str(path))
            opened = True
            factory.BeginInstantiate()
            instantiating = True
            for name, value in inputs:
                factory.PutInputData(name, value)
            for parameter in a["parameters"]:
                factory.GetParameter(parameter["name"]).ValuateFromString(parameter["value_with_unit"])
            obj = factory.Instantiate()
            if obj is not None:
                self.state.mark_created(obj, "feature")
        finally:
            try:
                if instantiating:
                    factory.EndInstantiate()
            finally:
                if opened:
                    factory.EndInstanceFactory()
        result = self.update(part)
        result["warning"] = "PowerCopy may return no object. Reread tree; no atomic rollback or template geometry guarantee."
        return result

    def visibility(self, a):
        records = [self.state.resolve(h) for h in a["handles"]]
        selection = self.conn.active_document.Selection
        if any(r.reference is not None for r in records):
            raise CADOperationError("UNSUPPORTED_OPERATION", "Show/hide accepts whole objects only")
        # Restoring a selected face via Value would silently restore its parent.
        if selection.Count2:
            raise CADOperationError("INVALID_ARGUMENT", "Clear selection explicitly first; exact subelement restoration is not guaranteed")
        try:
            for h, r in zip(a["handles"], records):
                self.changed(h)
                selection.Add(r.value)
            selection.VisProperties.SetShow(0 if a["visible"] else 1)
        finally:
            selection.Clear()
        return {"ok": True, "visible": a["visible"], "warning": "Visibility is not geometry; no geometric Update required"}
