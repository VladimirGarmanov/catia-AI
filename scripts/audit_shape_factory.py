"""Read-only inventory of all methods in the downloaded ShapeFactory snapshot.

Source mentions are NOT proof of callable coverage: the same method name can
belong to another factory. This report intentionally never labels them implemented.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
URL = "https://catiadesign.org/_doc/V5Automation/generated/interfaces/PartInterfaces/interface_ShapeFactory_20269.htm"


def inventory():
    cache = ROOT / ".local/v5-reference/pages" / (hashlib.sha256(URL.encode()).hexdigest() + ".json")
    payload = json.loads(cache.read_text(encoding="utf-8"))
    if payload.get("parser_version", 1) < 2:
        raise RuntimeError("Refresh PartInterfaces with sync_v5_reference.py --pages --match PartInterfaces --refresh; old parser omitted argument types")
    sources = {str(p.relative_to(ROOT)): p.read_text(encoding="utf-8").splitlines()
               for p in (ROOT / "catia_mcp").rglob("*.py")}
    methods = []
    for match in re.finditer(r"o Func\n(\w+)\n\(\n(.*?)\) As\n(\w+)", payload["text"], re.S):
        name, raw, result_type = match.groups()
        parameters = []
        for param in raw.strip().split("\n,\n") if raw.strip() else []:
            tokens = param.strip().splitlines()
            if len(tokens) != 2:
                raise RuntimeError(f"Cannot unambiguously parse {name}: {tokens}")
            parameters.append({"name": tokens[1], "type": tokens[0]})
        mentions = [f"{path}:{i}" for path, lines in sources.items()
                    for i, line in enumerate(lines, 1) if re.search(r"\b" + re.escape(name) + r"\b", line)]
        methods.append({"method": name, "parameters": parameters, "return_type": result_type,
                        "source_mentions": mentions, "callable_coverage": "not_established_by_this_audit",
                        "live_validation": "not_tested"})
    expected = re.findall(r"o Func\n(\w+)\n", payload["text"])
    if len(methods) != len(expected) or len({m["method"] for m in methods}) != len(expected):
        raise RuntimeError("Incomplete or duplicated ShapeFactory parse")
    return {"source": URL, "sha256": payload["sha256"], "method_count": len(methods), "methods": methods}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print complete native signature inventory")
    args = parser.parse_args()
    report = inventory()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Documented methods: {report['method_count']}; live validation: NOT TESTED")
        for item in report["methods"]:
            params = ", ".join(p["type"] + " " + p["name"] for p in item["parameters"])
            print(f"{item['method']}({params}) -> {item['return_type']}; source mentions={len(item['source_mentions'])}")
        print("Source mentions are not implementation or geometry validation evidence.")
