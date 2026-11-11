import hashlib
import json

import pytest

from catia_mcp.runtime import CADOperationError
from catia_mcp.tools.v5_reference import V5ReferenceTools

BASE = "https://example.test/V5Automation/"
FACTORY = BASE + "generated/interfaces/GSMInterfaces/interface_HybridShapeFactory_1.htm"
SHAPES = BASE + "generated/interfaces/PartInterfaces/interface_ShapeFactory_2.htm"
HOLE = BASE + "generated/interfaces/PartInterfaces/interface_Hole_3.htm"
BODIES = BASE + "generated/interfaces/MecModInterfaces/interface_Bodies_4.htm"
LIMIT = BASE + "generated/interfaces/PartInterfaces/enum_CatLimitMode_5.htm"
ARTICLE = BASE + "online/CAAPriPad.htm"

PAGES = {
    FACTORY: (1, """GSMInterfaces HybridShapeFactory (Object)
All Frameworks
HybridShapeFactory
(Object)
Method Index
AddNewPointTangent
Creates a new tangent to curve point.
Methods
o Func
AddNewPointTangent
(
iCurve
,
iDirection
) As
Creates a new tangent to curve point within the current body.
Parameters:
iCurve
Reference curve.
iDirection
Direction in which tangent points are computed
oPoint
Created point
o Sub
DeleteObjectForDatum
(
iObject
)
Deletes the object.
Copyright © 2003, Dassault Systèmes. All rights reserved."""),
    SHAPES: (2, """PartInterfaces ShapeFactory (Object)
All Frameworks
Methods
o Func
AddNewAdd
(
Body
iBodyToAdd
) As
Add
Creates and returns a new add operation within the current body.
Parameters:
iBodyToAdd
The body to add to the current body
Returns:
The created add operation
Example:
The following example adds body to the current body:
Set add = shapeFactory.
AddNewAdd
(body)
Copyright © 2003, Dassault Systèmes. All rights reserved."""),
    HOLE: (2, """PartInterfaces Hole (Object)
All Frameworks
Properties
o Property
BottomAngle
(
) As
Angle
(Read Only)
Returns the hole bottom angle.
Returns:
oBottomAngle    An Angle object
Example:
Set holeBottomAngle = firstHole.
BottomAngle
Methods
o Sub
SetOrigin
(
double
iX
,
double
iY
,
double
iZ
)
Sets the origin point which the hole is anchored to.
Parameters:
iX
Origin point x absolute coordinate
iY
Origin point y absolute coordinate
iZ
Origin point z absolute coordinate
Copyright © 2003, Dassault Systèmes. All rights reserved."""),
    BODIES: (2, """MecModInterfaces Bodies (Collection)
All Frameworks
Methods
o Func
Add
(
) As
Body
Creates a new body.
o Func
Item
(
CATVariant
iIndex
) As
Body
Returns a body.
Copyright © 2003, Dassault Systèmes. All rights reserved."""),
    LIMIT: (2, """PartInterfaces Enumeration CatLimitMode
All Frameworks
CatLimitMode
(Enumeration)
enum
CatLimitMode
{
  catOffsetLimit,
  catUpToNextLimit,
  catUpToLastLimit
}
Limit mode.
Values:
catOffsetLimit
The shape is limited by an offset value.
catUpToNextLimit
The shape is limited by the next boundary.
catUpToLastLimit
The shape is limited by the last boundary.
Copyright © 2003, Dassault Systèmes. All rights reserved."""),
    ARTICLE: (2, "Creating a Pad\nThis macro uses ShapeFactory.AddNewPad on a sketch and a filler sentence so the snippet window exceeds three hundred and twenty characters in total length for the purpose of this offline test of the snippet helper which trims around the hit."),
}
EXTRA_ITEM = BASE + "generated/interfaces/InfInterfaces/interface_Documents_6.htm"


def cache(tmp_path, pages=PAGES):
    (tmp_path / "pages").mkdir()
    entries = []
    for url, (version, text) in pages.items():
        title = text.split("\n", 1)[0]
        entries.append({"title": title, "url": url})
        page = {"url": url, "sha256": "x", "text": text}
        if version > 1:
            page["parser_version"] = version
        name = hashlib.sha256(url.encode()).hexdigest() + ".json"
        (tmp_path / "pages" / name).write_text(json.dumps(page), encoding="utf-8")
    (tmp_path / "index.json").write_text(json.dumps({"source": BASE, "source_kind": "test mirror", "entries": entries}), encoding="utf-8")
    return V5ReferenceTools(root=tmp_path)


def test_member_returns_only_typed_section_with_parameters(tmp_path):
    result = cache(tmp_path).execute("catia_v5_reference_member", {"member": "ShapeFactory.AddNewAdd"})
    assert result["signature"] == "Func AddNewAdd(Body iBodyToAdd) As Add"
    assert result["parameters"] == [{"name": "iBodyToAdd", "type": "Body", "description": "The body to add to the current body"}]
    assert result["returns"] == "Add" and result["returns_description"] == "The created add operation"
    assert "shapeFactory.AddNewAdd (body)" in result["example"]
    assert result["url"] == "generated/interfaces/PartInterfaces/interface_ShapeFactory_2.htm"
    assert result["types_extracted"] is True and result["live_validated"] is False and result["executable"] is False


def test_member_bare_name_v1_page_flags_missing_types(tmp_path):
    result = cache(tmp_path).execute("catia_v5_reference_member", {"member": "AddNewPointTangent"})
    assert result["interface"] == "HybridShapeFactory" and result["kind"] == "Func"
    assert result["signature"] == "Func AddNewPointTangent(iCurve, iDirection)"
    assert [p["description"] for p in result["parameters"]] == ["Reference curve.", "Direction in which tangent points are computed"]
    assert result["returns_description"] == "oPoint: Created point"
    assert result["types_extracted"] is False and "Parser v1" in result["warning"]
    sub = V5ReferenceTools(root=tmp_path).execute(
        "catia_v5_reference_member", {"member": "DeleteObjectForDatum", "interface": "HybridShapeFactory"})
    assert sub["kind"] == "Sub" and sub["signature"] == "Sub DeleteObjectForDatum(iObject)" and sub["returns"] is None


def test_member_property_and_sub_types(tmp_path):
    tools = cache(tmp_path)
    prop = tools.execute("catia_v5_reference_member", {"member": "Hole.BottomAngle"})
    assert prop["signature"] == "Property BottomAngle As Angle" and prop["read_only"] is True
    assert prop["example"] == "Set holeBottomAngle = firstHole.BottomAngle"
    sub = tools.execute("catia_v5_reference_member", {"member": "setorigin", "interface": "hole"})
    assert sub["signature"] == "Sub SetOrigin(double iX, double iY, double iZ)"
    assert [p["type"] for p in sub["parameters"]] == ["double"] * 3


def test_member_ambiguous_returns_candidates_not_guess(tmp_path):
    pages = dict(PAGES)
    pages[EXTRA_ITEM] = (2, "InfInterfaces Documents (Collection)\nMethods\no Func\nItem\n(\nCATVariant\niIndex\n) As\nDocument\nReturns a document.")
    result = cache(tmp_path, pages).execute("catia_v5_reference_member", {"member": "Item"})
    assert result["ambiguous"] is True and result["total"] == 2
    assert {c["interface"] for c in result["candidates"]} == {"Bodies", "Documents"}
    assert all("signature" not in c for c in result["candidates"])


def test_member_cap_and_invalid_inputs(tmp_path):
    tools = cache(tmp_path)
    capped = tools.execute("catia_v5_reference_member", {"member": "SetOrigin", "characters": 200})
    text = sum(len(capped[k]) for k in ("description", "returns_description", "example")) + sum(len(p["description"]) for p in capped["parameters"])
    assert text <= 200 and capped["signature"].startswith("Sub SetOrigin(")
    for bad in ({"member": "../index"}, {"member": "Hole.SetOrigin", "interface": "Pad"}):
        with pytest.raises(CADOperationError) as error:
            tools.execute("catia_v5_reference_member", bad)
        assert error.value.code == "INVALID_ARGUMENT"
    with pytest.raises(CADOperationError, match="inherited"):
        tools.execute("catia_v5_reference_member", {"member": "Hole.Name"})


def test_enum_values_are_zero_based_and_value_lookup(tmp_path):
    tools = cache(tmp_path)
    result = tools.execute("catia_v5_reference_enum", {"name": "CatLimitMode"})
    assert [(v["index"], v["name"]) for v in result["values"]] == [(0, "catOffsetLimit"), (1, "catUpToNextLimit"), (2, "catUpToLastLimit")]
    assert result["values"][1]["description"] == "The shape is limited by the next boundary."
    by_value = tools.execute("catia_v5_reference_enum", {"name": "catUpToLastLimit", "descriptions": False})
    assert by_value["enum"] == "CatLimitMode" and by_value["matched_value"] == {"name": "catUpToLastLimit", "index": 2}
    assert "description" not in by_value["values"][0]
    with pytest.raises(CADOperationError):
        tools.execute("catia_v5_reference_enum", {"name": "CatMissing"})


def test_enum_malformed_explicit_value_keeps_other_lookups_working(tmp_path):
    pages = dict(PAGES)
    pages[BASE + "generated/interfaces/PartInterfaces/enum_CatOdd_7.htm"] = (2, "PartInterfaces Enumeration CatOdd\nenum\nCatOdd\n{\n  catOddA = 01,\n  catOddB = catOddA | catOddC,\n  catOddC,\n  catOddD = 0x10,\n  catOddE\n}\nOdd.")
    tools = cache(tmp_path, pages)
    assert tools.execute("catia_v5_reference_enum", {"name": "CatLimitMode"})["values"][2]["index"] == 2
    assert {"name": "CatOdd", "kind": "Enumeration"} in tools.execute("catia_v5_reference_search", {"query": "catodd", "scope": "members"})["entries"]
    assert tools.execute("catia_v5_reference_member", {"member": "Hole.SetOrigin"})["kind"] == "Sub"
    odd = tools.execute("catia_v5_reference_enum", {"name": "catOddE"})
    assert [(v["name"], v["index"]) for v in odd["values"]] == [("catOddA", None), ("catOddB", None), ("catOddC", None), ("catOddD", 16), ("catOddE", 17)]
    assert odd["index_unresolved"] == ["catOddA", "catOddB", "catOddC"] and "unknown, not 0" in odd["warning"]
    assert odd["matched_value"] == {"name": "catOddE", "index": 17}
    assert "index_unresolved" not in tools.execute("catia_v5_reference_enum", {"name": "CatLimitMode"})


def test_cache_changing_during_sync_and_malformed_stored_index(tmp_path):
    tools = cache(tmp_path)
    files = tools._page_files()
    tools._page_files = lambda: files + [tmp_path / "pages" / "deleted-by-sync.json"]
    for name, args in (("catia_v5_reference_enum", {"name": "CatLimitMode"}), ("catia_v5_reference_search", {"query": "pad", "in_text": True})):
        with pytest.raises(CADOperationError) as error:
            tools.execute(name, args)
        assert error.value.code == "CAPABILITY_UNAVAILABLE" and "retry after sync" in str(error.value)
    fresh = V5ReferenceTools(root=tmp_path)
    (tmp_path / "members.json").write_text(json.dumps({"version": 1, "fingerprint": fresh._fingerprint(files), "pages": len(PAGES)}), encoding="utf-8")
    assert fresh.execute("catia_v5_reference_enum", {"name": "CatLimitMode"})["values"][0]["index"] == 0
    assert len(json.loads((tmp_path / "members.json").read_text(encoding="utf-8"))["interfaces"]) == 4


def test_member_index_persisted_versioned_and_rebuilt_when_pages_change(tmp_path):
    tools = cache(tmp_path)
    tools.execute("catia_v5_reference_search", {"query": "add", "scope": "members"})
    stored = json.loads((tmp_path / "members.json").read_text(encoding="utf-8"))
    assert stored["version"] == 1 and stored["pages"] == len(PAGES)
    extra = {"url": EXTRA_ITEM, "sha256": "y", "parser_version": 2,
             "text": "InfInterfaces Documents (Collection)\nMethods\no Func\nOpen\n(\nCATBSTR\niFileName\n) As\nDocument\nOpens a document."}
    (tmp_path / "pages" / (hashlib.sha256(EXTRA_ITEM.encode()).hexdigest() + ".json")).write_text(json.dumps(extra), encoding="utf-8")
    fresh = V5ReferenceTools(root=tmp_path)
    result = fresh.execute("catia_v5_reference_search", {"query": "documents.open", "scope": "members"})
    assert result["entries"] == [{"name": "Documents.Open", "kind": "Func"}]
    assert json.loads((tmp_path / "members.json").read_text(encoding="utf-8"))["pages"] == len(PAGES) + 1


def test_search_compact_default_full_text_and_legacy_rows(tmp_path):
    tools = cache(tmp_path)
    compact = tools.execute("catia_v5_reference_search", {"query": "hole"})
    assert compact["entries"] == [{"title": "PartInterfaces Hole (Object)", "url": "generated/interfaces/PartInterfaces/interface_Hole_3.htm"}]
    assert compact["base_url"] == BASE and compact["executable"] is False
    legacy = tools.execute("catia_v5_reference_search", {"query": "hole", "compact": False})
    assert legacy["entries"][0]["url"] == HOLE and legacy["source_kind"] == "test mirror"
    members = tools.execute("catia_v5_reference_search", {"query": "limit", "scope": "members"})
    assert {"name": "CatLimitMode", "kind": "Enumeration"} in members["entries"]
    hits = tools.execute("catia_v5_reference_search", {"query": "AddNewPad", "in_text": True})
    assert hits["total"] == 1 and hits["entries"][0]["url"] == "online/CAAPriPad.htm"
    snippet = hits["entries"][0]["snippet"]
    assert "ShapeFactory.AddNewPad" in snippet and len(snippet) <= len("addnewpad") + 320
    read = tools.execute("catia_v5_reference_read", {"url": compact["entries"][0]["url"], "characters": 100})
    assert read["url"] == HOLE and read["text"].startswith("PartInterfaces Hole")


def test_reference_tools_are_readonly_and_skip_catia_connection(tmp_path):
    from catia_mcp.server import CATIAMCPServer
    server = CATIAMCPServer()
    definitions = {d["name"]: d for d in server.v5_reference_tools.get_tool_definitions()}
    for name in ("catia_v5_reference_member", "catia_v5_reference_enum"):
        assert name in server.read_tool_names() and definitions[name]["readOnlyHint"] is True
        assert "request_id" not in server._schemas[name]["required"]
    server.v5_reference_tools = cache(tmp_path)
    server._tool_router["catia_v5_reference_enum"] = server.v5_reference_tools
    server.connection.ensure_connected = lambda: pytest.fail("reference lookup must not connect to CATIA")
    assert server._execute_serial("catia_v5_reference_enum", {"name": "CatLimitMode"})["values"][0]["index"] == 0


def test_missing_cache_is_capability_unavailable(tmp_path):
    with pytest.raises(CADOperationError) as error:
        V5ReferenceTools(root=tmp_path).execute("catia_v5_reference_enum", {"name": "CatLimitMode"})
    assert error.value.code == "CAPABILITY_UNAVAILABLE"
