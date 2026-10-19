"""Build a grep-friendly Fusion API reference from Fusion's own type stubs.

Usage:  python -I build_api_ref.py [path/to/defs/adsk]
Without a path, the newest Fusion install under %LOCALAPPDATA%/Autodesk/webdeploy is used.

Outputs (next to this script's parent folder, in api/):
  classes.txt   one line per class:  ns.Class(Base) [coll: Item] :: summary
  members.txt   one line per member: ns.Class.method(args) -> Ret :: summary
                                     ns.Class.prop: Type [rw|ro] :: summary
                                     ns.Enum.Value = 3
  ref/<ns>/<Class>.md   full documentation of one class (read only when needed)

The stubs are parsed with ast and never executed.
"""
import ast
import glob
import os
import re
import sys
import time
import warnings

NAMESPACES = ["core", "fusion", "cam", "drawing", "electron", "sim", "volume"]
SKIP = {"__init__", "cast", "__len__", "__getitem__", "__iter__"}
SUMMARY_MAX = 170


def find_defs():
    root = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Autodesk", "webdeploy", "production")
    hits = glob.glob(os.path.join(root, "*", "Api", "Python", "packages", "adsk", "defs", "adsk"))
    if not hits:
        sys.exit("Fusion API stubs not found; pass the defs/adsk folder as an argument.")
    return max(hits, key=lambda p: os.path.getmtime(os.path.join(p, "fusion.py")))


def clean(doc):
    return re.sub(r"\s+", " ", doc or "").strip()


def summary(doc):
    text = clean(doc)
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    s = m.group(1) if m else text
    return s if len(s) <= SUMMARY_MAX else s[: SUMMARY_MAX - 3] + "..."


def unparse(node):
    return ast.unparse(node) if node is not None else ""


def signature(fn):
    a = fn.args
    params = [p for p in a.args if p.arg != "self"]
    defaults = [None] * (len(params) - len(a.defaults)) + list(a.defaults)
    parts = []
    for p, d in zip(params, defaults):
        s = p.arg + (": " + unparse(p.annotation) if p.annotation else "")
        if d is not None:
            s += " = " + unparse(d)
        parts.append(s)
    ret = unparse(fn.returns)
    return "(" + ", ".join(parts) + ")" + (" -> " + ret if ret else "")


def decorators(fn):
    return {unparse(d) for d in fn.decorator_list}


def parse_class(cls):
    """Return dict with base, doc, enum values, methods, properties, collection item type."""
    info = {
        "name": cls.name,
        "bases": [unparse(b) for b in cls.bases],
        "doc": ast.get_docstring(cls) or "",
        "enums": [],
        "methods": [],
        "props": {},
        "item": None,
    }
    for node in cls.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    info["enums"].append((t.id, node.value.value))
        elif isinstance(node, ast.FunctionDef):
            decs = decorators(node)
            if node.name == "__getitem__":
                info["item"] = unparse(node.returns)
            if node.name in SKIP:
                continue
            doc = ast.get_docstring(node) or ""
            if "property" in decs:
                info["props"][node.name] = {"type": unparse(node.returns), "doc": doc, "rw": False}
            elif any(d.endswith(".setter") for d in decs):
                info["props"].setdefault(node.name, {"type": "", "doc": doc, "rw": True})["rw"] = True
            else:
                info["methods"].append(
                    {"name": node.name, "sig": signature(node), "doc": doc, "static": "staticmethod" in decs}
                )
    return info


def is_enum(info):
    return bool(info["enums"]) and not info["methods"] and not info["props"]


def full_doc_md(ns, info):
    out = [f"# {ns}.{info['name']}"]
    base = ", ".join(info["bases"])
    if base:
        out.append(f"Base: {base}")
    if info["item"]:
        out.append(f"Collection of: {info['item']}  (supports len(), [i], iteration)")
    out += ["", info["doc"].strip(), ""]
    if info["enums"]:
        out.append("## Values")
        out += [f"- {k} = {v}" for k, v in info["enums"]]
    if info["props"]:
        out.append("## Properties")
        for name, p in info["props"].items():
            out.append(f"### {name}: {p['type']} [{'rw' if p['rw'] else 'ro'}]")
            if p["doc"].strip():
                out.append(p["doc"].strip())
    if info["methods"]:
        out.append("## Methods")
        for m in info["methods"]:
            out.append(f"### {'static ' if m['static'] else ''}{m['name']}{m['sig']}")
            if m["doc"].strip():
                out.append(m["doc"].strip())
    return "\n".join(out).rstrip() + "\n"


def main():
    defs = sys.argv[1] if len(sys.argv) > 1 else find_defs()
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    api_dir = os.path.join(skill_dir, "api")
    os.makedirs(api_dir, exist_ok=True)
    stamp = f"# Generated {time.strftime('%Y-%m-%d')} from {defs}"

    class_lines, member_lines = [stamp], [stamp]
    counts = {}
    for ns in NAMESPACES:
        path = os.path.join(defs, ns + ".py")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f, warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)  # invalid escapes inside Autodesk's docstrings
            tree = ast.parse(f.read())
        ref_dir = os.path.join(api_dir, "ref", ns)
        os.makedirs(ref_dir, exist_ok=True)
        n = 0
        for cls in (c for c in tree.body if isinstance(c, ast.ClassDef)):
            info = parse_class(cls)
            q = f"{ns}.{info['name']}"
            n += 1
            if is_enum(info):
                class_lines.append(f"{q} [enum] :: {summary(info['doc'])}")
                member_lines += [f"{q}.{k} = {v}" for k, v in info["enums"]]
            else:
                base = f"({', '.join(info['bases'])})" if info["bases"] else ""
                coll = f" [coll: {info['item']}]" if info["item"] else ""
                class_lines.append(f"{q}{base}{coll} :: {summary(info['doc'])}")
                for name, p in info["props"].items():
                    member_lines.append(
                        f"{q}.{name}: {p['type']} [{'rw' if p['rw'] else 'ro'}] :: {summary(p['doc'])}"
                    )
                for m in info["methods"]:
                    if info["item"] and m["name"] == "item":
                        continue  # implied by [coll: X]
                    st = "static " if m["static"] else ""
                    member_lines.append(f"{st}{q}.{m['name']}{m['sig']} :: {summary(m['doc'])}")
            with open(os.path.join(ref_dir, info["name"] + ".md"), "w", encoding="utf-8") as f:
                f.write(full_doc_md(ns, info))
        counts[ns] = n

    for fname, lines in (("classes.txt", class_lines), ("members.txt", member_lines)):
        with open(os.path.join(api_dir, fname), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    print("classes per namespace:", counts)
    print("members.txt lines:", len(member_lines) - 1)


if __name__ == "__main__":
    main()
