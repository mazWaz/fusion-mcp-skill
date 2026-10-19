---
name: fusion-mcp
description: Use when working with Autodesk Fusion / Fusion 360 through the fusion MCP server (fusion_mcp_execute, fusion_mcp_read, http://127.0.0.1:27182/mcp) - modeling parts, enclosures or assemblies, editing a design, writing Fusion API Python scripts, looking up Fusion API classes/methods/enums, exporting STL/STEP/3MF, or reading Fusion Electronics data.
---

# Fusion MCP

Drive Fusion with short scripts built on the `fh` helper library, look API up in the local
grep-able reference (complete: 1,884 classes, 10k members), and verify with numbers before pixels.

## Script shape (every `fusion_mcp_execute` script)
```python
import sys, os, importlib; sys.path.insert(0, os.path.expanduser('~/.claude/skills/fusion-mcp/scripts'))
import fh; importlib.reload(fh); from fh import *

def run(_context: str):
    c = root()
    ...
    report()
```
fh units: lengths = mm numbers or expression strings (`'box_w/2'`, `'3 mm'`); angles = degrees.
Raw API (`ac` = adsk.core, `af` = adsk.fusion) stays cm / radians - use `vi()` / `P()`.

## Workflow
1. **Context** (readOnly script): `print(app().activeProduct.objectType)`, then `report()`. Not a
   `adsk::fusion::Design` -> `new_design()`. Never modify, close or save the user's documents
   unless asked; save only on explicit request.
2. **Parameters first**: `param('box_w', 42)` for every key dimension; drive features with names.
3. **Look up** any raw API before using it (API lookup below). Never guess signatures.
4. **Build in stages** (base body -> shell -> cuts/bosses -> details), one script per stage, each
   ending in `report()`. Model > ~40 lines or likely to iterate: write it to a `.py` file - the
   re-runnable parametric source is a deliverable, so keep it in the project the part belongs to
   (e.g. `fusion/<part>.py`; unrelated experiments go to the scratchpad) - as top-level code using fh names that starts with `scratch('<unique_tag>')`; run with `run_file(r'path')`;
   on error, Edit the file and re-run - do not resend whole scripts. A failed script keeps the
   features it made before the error (no rollback) - `scratch()` makes re-runs clean.
5. **Verify** against the spec from `report()` numbers (size, min corner, volume, timeline OK);
   for cuts, check *which* wall/face was hit (e.g. cylinder face positions of the feature).
   Screenshot only at milestones: `fit()` in the script, then `fusion_mcp_read` screenshot
   640x400, direction `iso-top-right`.
6. **Finish**: names, `material()` / `look()`, `export()` if asked.

## fh quick reference (c = component, sk = sketch, b = body)
| Area | Helpers |
|---|---|
| context | `app() design() root() new_design(tag) scratch(tag)` (empties only the never-saved doc it made with that tag, else opens a new one) `reset() health() report() fit()` |
| values | `vi(v, kind='mm'/'deg'/'n') P(x,y,z) V(x,y,z) mm(point)->tuple coll(items) param(name, expr, unit='mm')` |
| structure | `comp(name, parent=None) plane(c, 'xy'/'xz'/'yz'/face, offset=None) axis(c, 'x'/'y'/'z'/edge)` |
| sketch | `sketch(c, on, name, offset) sp(sk, x,y,z)->sketch xy  rect(sk,x0,y0,x1,y1) crect(sk,w,h,cx,cy) circle(sk, d, cx, cy)` (d = diameter) `poly(sk, pts, closed) rpoly(sk,n,d,cx,cy) slot(sk,x0,y0,x1,y1,w) arc3 spline text(sk, s, h, x0,y0,x1,y1)` |
| parametric sketch (fully constrained) | `pcrect(sk, w, h, cx=0, cy=0, construction=False)` rect centred at (cx, cy) -> 4 lines (corners `l.startSketchPoint`); `pcircles(sk, corner_pts, d)` equal circles; `pcircle(sk, d, x, y)` one circle from origin (0 = on axis); `dim(sk, a, b, v, 'h'/'v'/'a')`; `num(expr)` -> mm |
| profiles | `profs(sk) prof(sk,'largest'/'smallest'/i) prof_at(sk, x, y)` (face sketches also contain the face outline profile) |
| features | `extrude(c, prof, dist, op='new'/'join'/'cut'/'intersect'/'newcomp', sym, taper, to, rev, name)` dist: mm (negative = other side), expr (`rev=True` flips), `'all' '-all' 'all-both'`, `only=[body]` limits a cut to those bodies (else it cuts other components' bodies too); `revolve(c, prof, ax, angle, op, only)` fillet(c, edges, r) chamfer(c, edges, d) shell(c, faces, t) mirror(c, ents, plane) cpattern(c, ents, ax, n, angle) rpattern(c, ents, d1, n1, s1, d2, n2, s2) combine(c, target, tools, op, keep) move(c, ents, dx,dy,dz) rotate(c, ents, ax, deg)` `thread(c, face, 'M14x2', internal, clr)` (modeled, printed-fit clearance) |
| select | `bodies(c) body(c, i) faces(b, normal='z'/'-x'/(x,y,z), kind='plane'/'cyl'/..., where=fn) face_end(b, 'z', 'max'/'min') edges(src, kind='line'/'arc'/'circle', along='x'/'y'/'z', where=fn)` `thread_fit(fixed, moving, pitch)` (screw fit vs helix phase) |
| finish | `material(b, 'ABS Plastic') look(b_or_occ, 'Anodized') export(comp_or_occ, 'out/part.step'/.f3d)` (bodies: `.stl/.3mf/.obj`) `run_file(path, **globals)` |

Every feature helper returns the feature (`.bodies.item(0)` for the new body) and accepts `name=`
(timeline names are unique across sketches and features). Sketch normals: XY +Z, XZ +Y, YZ +X;
face sketches point out of the body, so cuts from them use `'-all'` / negative / `rev=True`.

## API lookup (`~/.claude/skills/fusion-mcp/api/`)
- `members.txt`: `ns.Class.method(args) -> Ret :: summary`, `ns.Class.prop: T [rw|ro]`,
  `ns.Enum.Value = n`, `static ns.Class.create(...)`. Grep: `^fusion\.HoleFeatures\.`,
  `^static fusion\.\w+\.create`, `^fusion\.ExtentDirections\.`.
- `classes.txt`: `ns.Class(Base) [coll: Item] :: summary` - discovery (`-i loft`). Members are listed
  on the class that defines them: not found -> grep the base class shown here.
- `ref/<ns>/<Class>.md`: full docs. Grep it with `-A 12` for one member instead of reading it all.
- Namespaces: `core` (geometry, app, UI, materials), `fusion` (design), `cam`, `drawing`,
  `electron`, `sim`, `volume`.
- Use `fusion_mcp_read` `apiDocumentation` only when the local files lack a name (Fusion updated);
  then rebuild: `python -I ~/.claude/skills/fusion-mcp/scripts/build_api_ref.py`.

## Output economy
- Print only what decides the next step: `report()` lines, counts, ids. No dumps of collections.
- Inspection scripts: `readOnly: true`. Several reads -> one script.
- Prefer one Grep line over a full reference file; prefer `report()` over screenshots.

## "Detailed" result checklist
- Key dimensions are user parameters; bodies, components and features have names.
- Separate parts = separate components (`comp()`), not just bodies.
- Exposed edges filleted/chamfered (fillet vertical edges before `shell`); realistic fits
  (3D print clearance 0.2-0.3 mm; M2 pilot 1.6-1.8 mm; M3 clearance 3.2-3.4 mm; printed threads:
  `clr=0.1` per part, lead-in after the thread, `thread_fit` free window > 0).
- Material/appearance set; timeline healthy; `report()` size equals the spec.

## When things fail
Read `reference/gotchas.md` (error text -> cause -> fix) - especially for face sketches, cuts,
text, parameters, units, components. Advanced features (constrained sketches, loft, sweep/pipe,
hole/counterbore, printed screw threads, split, construction planes, joints, draft): `reference/recipes.md`.
Electronics: `fusion_mcp_electronics_read` (read-only), schemas `resource://mcp.electronics_schema_<class>`.
