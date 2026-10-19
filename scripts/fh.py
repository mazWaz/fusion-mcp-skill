"""fh - compact helpers for driving Autodesk Fusion through fusion_mcp_execute.

Prelude for every MCP script (module level, before def run):
    import sys, os, importlib; sys.path.insert(0, os.path.expanduser('~/.claude/skills/fusion-mcp/scripts'))
    import fh; importlib.reload(fh); from fh import *

Units: lengths are mm (numbers) or Fusion expressions (str: 'wall*2', '3 mm', 'len/2');
angles are degrees (numbers) or expressions ('30 deg'). Raw API stays cm / radians.
Every feature helper takes the component first and returns the created feature.
"""
import math
import os
import sys

import adsk.core as ac
import adsk.fusion as af

__all__ = [
    "ac", "af", "OPS", "app", "design", "root", "new_design", "scratch", "reset", "vi", "P", "V", "coll",
    "param", "comp", "plane", "axis", "sketch", "sp", "rect", "crect", "circle", "poly", "rpoly",
    "slot", "arc3", "spline", "text", "num", "dim", "pcrect", "pcircles", "pcircle", "profs", "prof", "prof_at", "extrude", "revolve",
    "fillet", "chamfer", "shell", "mirror", "cpattern", "rpattern", "combine", "move",
    "rotate", "thread", "thread_fit", "bodies", "body", "faces", "face_end", "edges", "mm", "look", "material",
    "report", "health", "fit", "export", "run_file",
]

OPS = {
    "new": af.FeatureOperations.NewBodyFeatureOperation,
    "join": af.FeatureOperations.JoinFeatureOperation,
    "cut": af.FeatureOperations.CutFeatureOperation,
    "intersect": af.FeatureOperations.IntersectFeatureOperation,
    "newcomp": af.FeatureOperations.NewComponentFeatureOperation,
}
_POS = af.ExtentDirections.PositiveExtentDirection
_NEG = af.ExtentDirections.NegativeExtentDirection


# ---------- context ----------
def app():
    return ac.Application.get()


def design():
    d = af.Design.cast(app().activeProduct)
    if d is None:
        p = app().activeProduct
        raise RuntimeError(
            f"Active product is {p.objectType if p else None}, not a 3D Design. "
            "Use new_design() or activate a design document."
        )
    return d


def root():
    return design().rootComponent


def new_design(tag="default"):
    """Open a new, empty parametric design document tagged for scratch()/reset()."""
    app().documents.add(ac.DocumentTypes.FusionDesignDocumentType)
    d = design()
    d.designType = af.DesignTypes.ParametricDesignType
    d.attributes.add("fh", "scratch", tag)
    return d


def scratch(tag="default"):
    """Model-file entry point: empty the active design if new_design(tag) made it and it was never
    saved; otherwise open a new tagged design. Use a unique tag per model, e.g. scratch('mic_case')."""
    d = af.Design.cast(app().activeProduct)
    a = d.attributes.itemByName("fh", "scratch") if d else None
    if a and a.value == tag and not app().activeDocument.isSaved:
        reset()
        return d
    return new_design(tag)


def reset(force=False):
    """Delete the whole timeline so a model script can be re-run. Only for new_design() docs
    unless force=True (use force only with the user's explicit approval)."""
    d = design()
    if not force and (d.attributes.itemByName("fh", "scratch") is None or app().activeDocument.isSaved):
        raise RuntimeError("reset() refused: design was not created by new_design() or has been saved.")
    tl = d.timeline
    tl.moveToBeginning()
    tl.deleteAllAfterMarker()


# ---------- values ----------
def vi(v, kind="mm"):
    """ValueInput from mm number (kind='mm'), degrees (kind='deg'), unitless (kind='n') or expression str."""
    if isinstance(v, ac.ValueInput):
        return v
    if isinstance(v, str):
        return ac.ValueInput.createByString(v)
    if kind == "deg":
        return ac.ValueInput.createByReal(math.radians(v))
    if kind == "n":
        return ac.ValueInput.createByReal(v)
    return ac.ValueInput.createByReal(v / 10.0)


def P(x=0.0, y=0.0, z=0.0):
    """Point3D from mm."""
    return ac.Point3D.create(x / 10.0, y / 10.0, z / 10.0)


def V(x=0.0, y=0.0, z=0.0):
    return ac.Vector3D.create(x, y, z)


def mm(p, nd=3):
    """Point3D (cm) -> (x, y, z) tuple in mm, rounded."""
    return (round(p.x * 10, nd), round(p.y * 10, nd), round(p.z * 10, nd))


def coll(items):
    """ObjectCollection from a single entity, a list/tuple, or a Fusion collection."""
    if isinstance(items, ac.ObjectCollection):
        return items
    c = ac.ObjectCollection.create()
    if isinstance(items, (list, tuple)) or (hasattr(items, "count") and hasattr(items, "item")):
        for i in items:
            c.add(i)
    else:
        c.add(items)
    return c


def param(name, expr, unit="mm", comment=""):
    """Create or update a user parameter. expr: number (in `unit`) or expression str."""
    if isinstance(expr, (int, float)):
        expr = f"{expr} {unit}".strip()
    ups = design().userParameters
    p = ups.itemByName(name)
    if p:
        p.expression = expr
        return p
    return ups.add(name, ac.ValueInput.createByString(expr), unit, comment)


# ---------- structure ----------
def comp(name, parent=None):
    """New child component (returns the Component; its occurrence is comp.occurrences' parent)."""
    occ = (parent or root()).occurrences.addNewComponent(ac.Matrix3D.create())
    occ.component.name = name
    return occ.component


def plane(c, on="xy", offset=None):
    """'xy'|'xz'|'yz'|planar face|construction plane, optionally offset (mm/expr)."""
    base = on
    if isinstance(on, str):
        base = {"xy": c.xYConstructionPlane, "xz": c.xZConstructionPlane, "yz": c.yZConstructionPlane}[on.lower()]
    if not offset:
        return base
    inp = c.constructionPlanes.createInput()
    inp.setByOffset(base, vi(offset))
    return c.constructionPlanes.add(inp)


def axis(c, a="z"):
    """'x'|'y'|'z' construction axis of c, or any linear entity passed through."""
    if isinstance(a, str):
        return {"x": c.xConstructionAxis, "y": c.yConstructionAxis, "z": c.zConstructionAxis}[a.lower()]
    return a


# ---------- sketches (coordinates are sketch-space mm) ----------
def sketch(c, on="xy", name=None, offset=None):
    sk = c.sketches.add(plane(c, on, offset))
    if name:
        sk.name = name
    return sk


def sp(sk, x=0.0, y=0.0, z=0.0):
    """Model-space mm point -> sketch-space (x, y) mm for sketches on faces / xz / yz planes."""
    p = sk.modelToSketchSpace(P(x, y, z))
    return (p.x * 10, p.y * 10)


def rect(sk, x0, y0, x1, y1):
    return sk.sketchCurves.sketchLines.addTwoPointRectangle(P(x0, y0), P(x1, y1))


def crect(sk, w, h, cx=0, cy=0):
    return sk.sketchCurves.sketchLines.addCenterPointRectangle(P(cx, cy), P(cx + w / 2, cy + h / 2))


def circle(sk, d, cx=0, cy=0):
    """Circle by DIAMETER d (mm)."""
    return sk.sketchCurves.sketchCircles.addByCenterRadius(P(cx, cy), d / 20.0)


def poly(sk, pts, closed=True):
    """Connected polyline through [(x, y), ...]; closed by default."""
    lines, out = sk.sketchCurves.sketchLines, []
    p3 = [P(*p) for p in pts]
    for i in range(1, len(p3)):
        out.append(lines.addByTwoPoints(out[-1].endSketchPoint if out else p3[0], p3[i]))
    if closed:
        out.append(lines.addByTwoPoints(out[-1].endSketchPoint, out[0].startSketchPoint))
    return out


def rpoly(sk, n, d, cx=0, cy=0, rot=0):
    """Regular n-gon with circumscribed diameter d (mm), rotated rot degrees."""
    r = d / 2
    return poly(sk, [(cx + r * math.cos(math.radians(rot + 360 * i / n)),
                      cy + r * math.sin(math.radians(rot + 360 * i / n))) for i in range(n)])


def slot(sk, x0, y0, x1, y1, w):
    """Center-to-center slot of width w."""
    return sk.addCenterToCenterSlot(P(x0, y0), P(x1, y1), vi(w))


def arc3(sk, p0, pm, p1):
    return sk.sketchCurves.sketchArcs.addByThreePoints(P(*p0), P(*pm), P(*p1))


def spline(sk, pts):
    return sk.sketchCurves.sketchFittedSplines.add(coll([P(*p) for p in pts]))


def text(sk, s, h, x0, y0, x1, y1, font=None, expr=False):
    """Text centered in the box (x0,y0)-(x1,y1), height h mm. expr=True: s is a text
    expression like "'V' + ver" (plain text is quoted automatically)."""
    st = sk.sketchTexts
    inp = st.createInput3(s if expr else "'" + s.replace("'", "\\'") + "'", vi(h))
    inp.setAsMultiLine(P(x0, y0), P(x1, y1), ac.HorizontalAlignments.CenterHorizontalAlignment,
                       ac.VerticalAlignments.MiddleVerticalAlignment, 0)
    if font:
        inp.fontName = font
    return st.add(inp)


# ---------- parametric (fully constrained) sketches ----------
_DIMO = {"h": af.DimensionOrientations.HorizontalDimensionOrientation,
         "v": af.DimensionOrientations.VerticalDimensionOrientation,
         "a": af.DimensionOrientations.AlignedDimensionOrientation}


def num(v):
    """mm value of a number or expression ('box_w - 2*boss_inset')."""
    if isinstance(v, (int, float)):
        return float(v)
    return design().unitsManager.evaluateExpression(v, "mm") * 10


def _expr(v):
    """Positive dimension expression for a signed coordinate (number or expr)."""
    if isinstance(v, (int, float)):
        return f"{abs(v)} mm"
    s = v.strip()
    if num(s) >= 0:
        return s
    return s[1:] if s.startswith("-") and "+" not in s[1:] and "-" not in s[1:] else f"-({s})"


def dim(sk, a, b, v, orient="h", at=None):
    """Driving distance dimension between sketch points a, b ('h'|'v'|'a'); v = mm or expression."""
    if at is None:
        ga, gb = a.geometry, b.geometry
        at = ac.Point3D.create((ga.x + gb.x) / 2 + 0.3, (ga.y + gb.y) / 2 + 0.3, 0)
    d = sk.sketchDimensions.addDistanceDimension(a, b, _DIMO[orient], at)
    d.parameter.expression = _expr(v)
    return d


def _locate(sk, pt, x, y):
    """Constrain sketch point pt at (x, y) from the sketch origin (0 -> on that axis)."""
    xn, yn = num(x), num(y)
    o, gc = sk.originPoint, sk.geometricConstraints
    if abs(xn) < 1e-9 and abs(yn) < 1e-9:
        gc.addCoincident(pt, o)
        return
    if abs(xn) < 1e-9 or abs(yn) < 1e-9:
        ln = sk.sketchCurves.sketchLines.addByTwoPoints(o, pt)
        ln.isConstruction = True
        (gc.addVertical if abs(xn) < 1e-9 else gc.addHorizontal)(ln)
    if abs(xn) > 1e-9:
        dim(sk, o, pt, x, "h", P(xn / 2, yn + 3))
    if abs(yn) > 1e-9:
        dim(sk, o, pt, y, "v", P(xn + 3, yn / 2))


def pcrect(sk, w, h, cx=0, cy=0, construction=False):
    """Fully constrained rectangle w x h centred at (cx, cy) from the sketch origin (all mm or
    expressions; sketch coords). Returns its 4 lines; corners = [l.startSketchPoint for l in lines]."""
    wn, hn, cxn, cyn = num(w), num(h), num(cx), num(cy)
    ls = list(crect(sk, wn, hn, cxn, cyn))
    gc = sk.geometricConstraints
    for ln in ls:
        s, e = ln.startSketchPoint.geometry, ln.endSketchPoint.geometry
        (gc.addHorizontal if abs(s.y - e.y) < 1e-9 else gc.addVertical)(ln)
        ln.isConstruction = construction
    diag = sk.sketchCurves.sketchLines.addByTwoPoints(ls[0].startSketchPoint, ls[1].endSketchPoint)
    diag.isConstruction = True
    if abs(cxn) < 1e-9 and abs(cyn) < 1e-9:
        gc.addMidPoint(sk.originPoint, diag)
    else:
        mid = sk.sketchPoints.add(P(cxn, cyn))
        gc.addMidPoint(mid, diag)
        _locate(sk, mid, cx, cy)
    hl = next(l for l in ls if abs(l.startSketchPoint.geometry.y - l.endSketchPoint.geometry.y) < 1e-9)
    vl = next(l for l in ls if l is not hl and abs(l.startSketchPoint.geometry.x - l.endSketchPoint.geometry.x) < 1e-9)
    dim(sk, hl.startSketchPoint, hl.endSketchPoint, w, "h", P(cxn, cyn - hn / 2 - 4))
    dim(sk, vl.startSketchPoint, vl.endSketchPoint, h, "v", P(cxn + wn / 2 + 4, cyn))
    return ls


def pcircles(sk, centers, d):
    """Equal circles (diameter d, mm/expr) on existing sketch points (e.g. pcrect corners); one
    diameter dimension + equal constraints. Returns the circles."""
    circles = sk.sketchCurves.sketchCircles
    cs = [circles.addByCenterRadius(p, num(d) / 20) for p in centers]
    pd = cs[0].centerSketchPoint.geometry
    sk.sketchDimensions.addDiameterDimension(cs[0], ac.Point3D.create(pd.x + 0.5, pd.y + 0.5, 0)).parameter.expression = _expr(d)
    for ci in cs[1:]:
        sk.geometricConstraints.addEqual(cs[0], ci)
    return cs


def pcircle(sk, d, x=0, y=0):
    """One circle located from the sketch origin by x/y (sketch coords; mm or expressions; 0 =
    on that axis) with a diameter dimension. For several circles use pcrect corners + pcircles."""
    xn, yn = num(x), num(y)
    ci = sk.sketchCurves.sketchCircles.addByCenterRadius(P(xn, yn), num(d) / 20)
    _locate(sk, ci.centerSketchPoint, x, y)
    sk.sketchDimensions.addDiameterDimension(ci, P(xn + num(d) / 2 + 1, yn + num(d) / 2 + 1)).parameter.expression = _expr(d)
    return ci


def profs(sk):
    return list(sk.profiles)


def prof(sk, which="largest"):
    """Profile by 'largest' | 'smallest' area or index."""
    ps = profs(sk)
    if isinstance(which, int):
        return ps[which]
    ps.sort(key=lambda p: p.areaProperties().area)
    return ps[-1] if which == "largest" else ps[0]


def prof_at(sk, x, y):
    """Smallest profile whose bounding box contains sketch point (x, y) mm."""
    hits = []
    for p in sk.profiles:
        bb = p.boundingBox
        if bb.minPoint.x <= x / 10 <= bb.maxPoint.x and bb.minPoint.y <= y / 10 <= bb.maxPoint.y:
            hits.append(p)
    if not hits:
        raise RuntimeError(f"no profile contains ({x}, {y})")
    return min(hits, key=lambda p: p.areaProperties().area)


# ---------- features ----------
def _named(f, name):
    if name:
        f.name = name
        if f.name != name:
            print(f"note: name '{name}' already used in timeline -> '{f.name}'")
    return f


def _only(inp, only):
    """Limit a cut/intersect to these bodies (default: every body it touches, in ANY component)."""
    if only is not None:
        inp.participantBodies = list(only) if isinstance(only, (list, tuple)) else [only]


def extrude(c, profile, dist, op="new", sym=False, taper=0, to=None, rev=False, name=None, only=None):
    """dist: mm (negative = opposite side) | expr | 'all' | '-all' | 'all-both'.
    rev=True flips the side (use with expressions: extrude(c, p, 'pilot_depth', 'cut', rev=True)).
    sym=True: dist is the full symmetric length. to=face/plane: extrude up to entity.
    only=body/[bodies]: cut/intersect just these (else overlapping bodies of other components too)."""
    ef = c.features.extrudeFeatures
    inp = ef.createInput(coll(profile) if isinstance(profile, (list, tuple)) else profile, OPS[op])
    _only(inp, only)
    t = vi(taper, "deg") if taper else None
    if to is not None:
        inp.setOneSideExtent(af.ToEntityExtentDefinition.create(to, False), _POS, t)
    elif dist == "all-both":
        inp.setTwoSidesExtent(af.ThroughAllExtentDefinition.create(), af.ThroughAllExtentDefinition.create())
    elif dist in ("all", "-all"):
        ta = af.ThroughAllExtentDefinition.create()
        ta.isPositiveDirection = dist == "all"  # the setOneSideExtent direction alone is ignored
        inp.setOneSideExtent(ta, _POS if dist == "all" else _NEG)
    elif sym:
        inp.setSymmetricExtent(vi(dist), True, t)
    else:
        neg = (isinstance(dist, (int, float)) and dist < 0) != bool(rev)
        dv = vi(abs(dist)) if isinstance(dist, (int, float)) else vi(dist)
        inp.setOneSideExtent(af.DistanceExtentDefinition.create(dv), _NEG if neg else _POS, t)
    return _named(ef.add(inp), name)


def revolve(c, profile, ax, angle=360, op="new", sym=False, name=None, only=None):
    """ax: 'x'|'y'|'z' or a linear entity (e.g. a sketch line on the profile sketch); only: see extrude."""
    rf = c.features.revolveFeatures
    inp = rf.createInput(profile, axis(c, ax), OPS[op])
    inp.setAngleExtent(sym, vi(angle, "deg"))
    _only(inp, only)
    return _named(rf.add(inp), name)


def fillet(c, edges, r, tangent=True, name=None):
    ff = c.features.filletFeatures
    inp = ff.createInput()
    inp.edgeSetInputs.addConstantRadiusEdgeSet(coll(edges), vi(r), tangent)
    return _named(ff.add(inp), name)


def chamfer(c, edges, d, tangent=True, name=None):
    cf = c.features.chamferFeatures
    inp = cf.createInput2()
    inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(coll(edges), vi(d), tangent)
    return _named(cf.add(inp), name)


def shell(c, faces_or_body, t, outside=False, name=None):
    """Remove the given faces and hollow the body to wall thickness t (pass a body for a closed shell)."""
    sf = c.features.shellFeatures
    inp = sf.createInput(coll(faces_or_body), False)
    if outside:
        inp.outsideThickness = vi(t)
    else:
        inp.insideThickness = vi(t)
    return _named(sf.add(inp), name)


def mirror(c, entities, pl, combine=False, name=None):
    mf = c.features.mirrorFeatures
    inp = mf.createInput(coll(entities), plane(c, pl))
    inp.isCombine = combine
    return _named(mf.add(inp), name)


def cpattern(c, entities, ax, n, angle=360, sym=False, name=None):
    """Circular pattern of bodies/features/faces: n copies over angle degrees."""
    pf = c.features.circularPatternFeatures
    inp = pf.createInput(coll(entities), axis(c, ax))
    inp.quantity = vi(n, "n")
    inp.totalAngle = vi(angle, "deg")
    inp.isSymmetric = sym
    return _named(pf.add(inp), name)


def rpattern(c, entities, d1, n1, s1, d2=None, n2=1, s2=0, name=None):
    """Rectangular pattern; s1/s2 are spacings (mm/expr) along axes d1/d2 ('x'|'y'|'z'|edge)."""
    pf = c.features.rectangularPatternFeatures
    inp = pf.createInput(coll(entities), axis(c, d1), vi(n1, "n"), vi(s1),
                         af.PatternDistanceType.SpacingPatternDistanceType)
    if d2 is not None:
        inp.setDirectionTwo(axis(c, d2), vi(n2, "n"), vi(s2))
    return _named(pf.add(inp), name)


def combine(c, target, tools, op="join", keep=False, name=None):
    cf = c.features.combineFeatures
    inp = cf.createInput(target, coll(tools))
    inp.operation = OPS[op]
    inp.isKeepToolBodies = keep
    return _named(cf.add(inp), name)


def move(c, ents, dx=0, dy=0, dz=0, name=None):
    mf = c.features.moveFeatures
    inp = mf.createInput2(coll(ents))
    inp.defineAsTranslateXYZ(vi(dx), vi(dy), vi(dz), True)
    return _named(mf.add(inp), name)


def rotate(c, ents, ax, angle, name=None):
    mf = c.features.moveFeatures
    inp = mf.createInput2(coll(ents))
    inp.defineAsRotate(axis(c, ax), vi(angle, "deg"))
    return _named(mf.add(inp), name)


def thread(c, face, desig, internal=False, clr=0, cls=None, name=None):
    """Modeled ISO metric thread ('M14x2') on a cylindrical face (stud: Ø = major; bore: Ø ~ minor).
    clr (mm/expr) is offset into this part's flank/root faces for 3D-printed fits (0.1 on each
    part = 0.2 total). Thread the full cylinder FIRST, then cut lead-ins (see recipes)."""
    tt = af.ThreadDataQuery.create(False).defaultMetricThreadType
    info = af.ThreadInfo.create(False, internal, tt, desig, cls or ("6H" if internal else "6g"), True)
    ti = c.features.threadFeatures.createInput(coll(face), info)
    ti.isFullLength = True
    ti.isModeled = True
    tf = _named(c.features.threadFeatures.add(ti), name)
    if clr:
        d = vi(-clr) if isinstance(clr, (int, float)) else vi(f"-({clr})")
        oi = c.features.offsetFacesFeatures.createInput(list(tf.faces), d)
        _named(c.features.offsetFacesFeatures.add(oi), name and name + " Clearance")
    return tf


def thread_fit(fixed, moving, pitch, step=2, center=(0, 0)):
    """Mating modeled threads overlap at most rotations (helix phase), so a plain interference
    check is meaningless. Spins a temporary copy of `moving` 360 deg about the Z axis through
    center (x, y mm) and intersects it with `fixed` (read-only safe; pass occurrence bodies).
    Returns (max_mm3, min_mm3, free_deg, axial_play_mm); a good fit has free_deg > 0."""
    tm = af.TemporaryBRepManager.get()
    vols = []
    for deg in range(0, 360, step):
        t = tm.copy(moving)
        m = ac.Matrix3D.create()
        m.setToRotation(math.radians(deg), V(0, 0, 1), P(*center))
        tm.transform(t, m)
        g = tm.copy(fixed)
        tm.booleanOperation(g, t, af.BooleanTypes.IntersectionBooleanType)
        vols.append(g.volume * 1000 if g.faces.count else 0.0)
    free = sum(1 for v in vols if v < 1e-3) * step
    return max(vols), min(vols), free, free * pitch / 360


# ---------- selection ----------
def bodies(c=None):
    return list((c or root()).bRepBodies)


def body(c=None, i=-1):
    return bodies(c)[i]


_STYPES = {"plane": ac.SurfaceTypes.PlaneSurfaceType, "cyl": ac.SurfaceTypes.CylinderSurfaceType,
           "cone": ac.SurfaceTypes.ConeSurfaceType, "sphere": ac.SurfaceTypes.SphereSurfaceType,
           "torus": ac.SurfaceTypes.TorusSurfaceType}
_CTYPES = {"line": ac.Curve3DTypes.Line3DCurveType, "arc": ac.Curve3DTypes.Arc3DCurveType,
           "circle": ac.Curve3DTypes.Circle3DCurveType}
_AX = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1), "-x": (-1, 0, 0), "-y": (0, -1, 0), "-z": (0, 0, -1)}


def faces(b, normal=None, kind=None, where=None, tol=1e-4):
    """Faces of body b. normal: 'z'|'-x'|(x,y,z) outward normal; kind: plane|cyl|cone|sphere|torus;
    where: callable(face) -> bool (use mm(f.pointOnFace))."""
    nv = None
    if normal is not None:
        nv = V(*_AX.get(normal, normal) if isinstance(normal, str) else normal)
        nv.normalize()
    out = []
    for f in b.faces:
        if kind and f.geometry.surfaceType != _STYPES[kind]:
            continue
        if nv is not None:
            ok, n = f.evaluator.getNormalAtPoint(f.pointOnFace)
            if not ok or n.dotProduct(nv) < 1 - tol:
                continue
        if where and not where(f):
            continue
        out.append(f)
    return out


def face_end(b, ax="z", end="max"):
    """Planar face at the max/min end of body b along axis ('z' -> top face)."""
    i = "xyz".index(ax)
    fs = faces(b, normal=ax if end == "max" else "-" + ax, kind="plane")
    if not fs:
        raise RuntimeError(f"no planar face facing {'' if end == 'max' else '-'}{ax}")
    key = lambda f: mm(f.pointOnFace)[i]
    return max(fs, key=key) if end == "max" else min(fs, key=key)


def edges(src, kind=None, along=None, where=None, tol=1e-6):
    """Edges of a body, face or list of faces. kind: line|arc|circle; along: 'x'|'y'|'z'
    (straight edges parallel to axis); where: callable(edge) -> bool (use mm(e.pointOnEdge))."""
    if isinstance(src, (list, tuple)):
        es = {e.tempId: e for f in src for e in f.edges}.values()
    else:
        es = list(src.edges)
    out = []
    for e in es:
        g = e.geometry
        if kind and g.curveType != _CTYPES[kind]:
            continue
        if along:
            if g.curveType != ac.Curve3DTypes.Line3DCurveType:
                continue
            d = g.startPoint.vectorTo(g.endPoint)
            d.normalize()
            if abs(abs(d.dotProduct(V(*_AX[along]))) - 1) > tol:
                continue
        if where and not where(e):
            continue
        out.append(e)
    return out


# ---------- appearance / material ----------
def _by_name(items, name):
    try:
        return items.itemByName(name)  # library collections raise instead of returning None
    except RuntimeError:
        return None


def _find_in_libs(attr, name):
    libs = app().materialLibraries
    partial = None
    for i in range(libs.count):
        try:
            items = getattr(libs.item(i), attr)
        except Exception:
            continue
        hit = _by_name(items, name)
        if hit:
            return hit
        if partial is None:
            for j in range(items.count):
                it = items.item(j)
                if name.lower() in it.name.lower():
                    partial = it
                    break
    if partial is None:
        raise RuntimeError(f"no {attr[:-1]} matching '{name}'")
    return partial


def look(target, name):
    """Apply an appearance (exact or substring name, e.g. 'Aluminum - Anodized Black') to a body/occurrence."""
    d = design()
    a = _by_name(d.appearances, name)
    if a is None:
        src = _find_in_libs("appearances", name)
        a = _by_name(d.appearances, src.name) or d.appearances.addByCopy(src, src.name)
    target.appearance = a
    return a.name


def material(b, name):
    """Assign a physical material (exact or substring name, e.g. 'ABS Plastic') to a body."""
    b.material = _find_in_libs("materials", name)
    return b.material.name


# ---------- verification ----------
def health():
    d = design()
    if d.designType != af.DesignTypes.ParametricDesignType:
        return []
    tl, bad = d.timeline, []
    for i in range(tl.count):
        it = tl.item(i)
        if it.healthState != af.FeatureHealthStates.HealthyFeatureHealthState:
            bad.append(f"{it.name}: {it.errorOrWarningMessage}")
    return bad


def _body_line(b, phys):
    bb = b.boundingBox
    lo, hi = mm(bb.minPoint, 2), mm(bb.maxPoint, 2)
    size = tuple(round(h - l, 2) for l, h in zip(lo, hi))
    s = f"  {b.name}: {'solid' if b.isSolid else 'surface'} size={size} min={lo} F{b.faces.count} E{b.edges.count}"
    if phys and b.isSolid:
        pp = b.physicalProperties
        s += f" vol={pp.volume * 1000:.1f}mm3 mass={pp.mass * 1000:.1f}g"
    return s


def report(phys=True):
    """Print a compact model summary (world coords, mm) and timeline health; returns the lines."""
    d, r = design(), root()
    lines = [f"design '{app().activeDocument.name}' units={d.unitsManager.defaultLengthUnits} "
             f"params={d.userParameters.count}"]
    lines.append(f"root: {r.bRepBodies.count} bodies, {r.sketches.count} sketches")
    lines += [_body_line(b, phys) for b in r.bRepBodies]
    for occ in r.allOccurrences:
        lines.append(f"occ {occ.fullPathName}: {occ.bRepBodies.count} bodies")
        lines += [_body_line(b, phys) for b in occ.bRepBodies]
    bad = health()
    n = d.timeline.count if d.designType == af.DesignTypes.ParametricDesignType else 0
    lines.append(f"timeline {n} items: " + ("OK" if not bad else "PROBLEMS -> " + " | ".join(bad)))
    print("\n".join(lines))
    return lines


def fit():
    """Zoom the viewport to fit all geometry (call before an MCP screenshot)."""
    app().activeViewport.fit()


# ---------- export / files ----------
def export(target, path, fmt=None, refine="high"):
    """Export a component/occurrence/body to stl|3mf|obj|step|iges|sat|f3d by extension."""
    path = os.path.abspath(os.path.expanduser(path))
    fmt = (fmt or os.path.splitext(path)[1][1:]).lower()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    em = design().exportManager
    mesh = {"stl": em.createSTLExportOptions, "3mf": em.createC3MFExportOptions, "obj": em.createOBJExportOptions}
    cad = {"step": em.createSTEPExportOptions, "stp": em.createSTEPExportOptions, "iges": em.createIGESExportOptions,
           "igs": em.createIGESExportOptions, "sat": em.createSATExportOptions, "f3d": em.createFusionArchiveExportOptions}
    if fmt in mesh:
        o = mesh[fmt](target, path)
        if fmt == "stl":
            o.meshRefinement = {"high": af.MeshRefinementSettings.MeshRefinementHigh,
                                "medium": af.MeshRefinementSettings.MeshRefinementMedium,
                                "low": af.MeshRefinementSettings.MeshRefinementLow}[refine]
    elif fmt in cad:
        if isinstance(target, af.Occurrence):
            target = target.component
        if isinstance(target, af.BRepBody):
            raise ValueError(f"{fmt} export needs a component (body.parentComponent) - or use stl/3mf/obj")
        o = cad[fmt](path, target)
    else:
        raise ValueError(f"unsupported format {fmt}")
    if not em.execute(o):
        raise RuntimeError(f"export failed: {path}")
    return path


def run_file(path, **kw):
    """Execute a model script file with all fh helpers in scope (keeps long scripts on disk:
    edit the file, then re-run with a 3-line MCP call). Extra kwargs become globals."""
    path = os.path.abspath(os.path.expanduser(path))
    g = {"__name__": "__fh_model__", "__file__": path, "os": os, "math": math, "fh": sys.modules[__name__]}
    g.update({k: globals()[k] for k in __all__})
    g.update(kw)
    with open(path, encoding="utf-8") as f:
        code = compile(f.read(), path, "exec")
    exec(code, g)
    return g
