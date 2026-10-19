# Raw-API recipes (beyond fh helpers)

All snippets assume the fh prelude (`from fh import *`), `c = root()` (or a component),
mm via `vi()` / `P()`. Each recipe was run in Fusion 2705; adapt, don't re-derive.

## Contents
- Fully-constrained parametric sketch (dimensions + constraints)
- Loft between offset sections
- Sweep / pipe along a path
- Hole feature (counterbore / countersink / simple) at sketch points
- Modeled thread on a cylinder (standard designation lookup)
- Split body (e.g. lid / base)
- Construction planes: angle, midplane, along path
- Body -> component, joints (rigid / revolute), grounding
- Draft, offset faces, sheet of points

## Parametric sketch: dimensions + constraints
Prefer the fh helpers (tested fully constrained): `pcrect(sk, 'box_w', 'box_d')` (centred
outline), `pcrect(..., construction=True)` + `pcircles(sk, [l.startSketchPoint for l in lines], 'boss_d')`
(hole/boss grids), `pcircle(sk, 'mic_d', 0, '-mic_z')` (single hole), off-centre cutout on XZ:
`pcrect(sk, 'usb_w', 'usb_h', 0, '-usb_z')`, any dimension: `dim(sk, a, b, expr, 'h'|'v'|'a')`.
Raw API equivalent:
```python
sk = sketch(c, 'xy', 'plate_dims')
lines = crect(sk, 40, 25)                      # SketchLineList, 4 lines, NO constraints yet
dims, gc = sk.sketchDimensions, sk.geometricConstraints
gc.addHorizontal(lines[0]); gc.addHorizontal(lines[2]); gc.addVertical(lines[1]); gc.addVertical(lines[3])
H = af.DimensionOrientations.HorizontalDimensionOrientation
V_ = af.DimensionOrientations.VerticalDimensionOrientation
dw = dims.addDistanceDimension(lines[0].startSketchPoint, lines[0].endSketchPoint, H, P(0, -16))
dh = dims.addDistanceDimension(lines[1].startSketchPoint, lines[1].endSketchPoint, V_, P(24, 0))
dw.parameter.expression = 'box_w'              # drive from user parameters
dh.parameter.expression = 'box_d'
hole = circle(sk, 3.2, 15, 8)
dims.addDiameterDimension(hole, P(18, 11)).parameter.expression = 'hole_d'
print(sk.isFullyConstrained)                   # False until every point is located
```
Centering: `gc.addMidPoint(sk.originPoint, diagonal_line)` with a construction diagonal
(`ln.isConstruction = True`). Read back a dimension: `dw.parameter.value` (cm).

## Loft between offset sections
```python
s0 = sketch(c, 'xy', 'loft0'); crect(s0, 30, 30)
s1 = sketch(c, 'xy', 'loft1', offset=20); circle(s1, 16)
lf = c.features.loftFeatures
li = lf.createInput(OPS['new'])
li.loftSections.add(prof(s0)); li.loftSections.add(prof(s1))
li.isSolid = True
loft = lf.add(li)
```
Rails / centerline: `li.centerLineOrRails.addRail(curve)` / `.addCenterLine(curve)`.

## Sweep / pipe along a path
```python
path_sk = sketch(c, 'xz', 'path')
pl = poly(path_sk, [(0, 0), (0, -20), (15, -30)], closed=False)
path = af.Path.create(coll(pl), af.ChainedCurveOptions.connectedChainedCurves)
prof_sk = sketch(c, 'xy', 'sweep_prof'); circle(prof_sk, 4)
sw = c.features.sweepFeatures
si = sw.createInput(prof(prof_sk), path, OPS['new'])
si.orientation = af.SweepOrientationTypes.PerpendicularOrientationType
sweep = sw.add(si)
# Pipe (no profile sketch; hollow optional):
pi = c.features.pipeFeatures.createInput(path, OPS['new'])
pi.sectionSize = vi(3); pi.isHollow = True; pi.sectionThickness = vi(0.5)
c.features.pipeFeatures.add(pi)
```
A profile must touch / be perpendicular to the path start or the sweep fails.

## Hole feature (counterbore / countersink / simple)
```python
hs = sketch(c, face_end(b, 'z', 'max'), 'hole_pts')
pts = coll([hs.sketchPoints.add(P(*sp(hs, x, y))) for x, y in [(-15, -8), (15, 8)]])
hf = c.features.holeFeatures
hi = hf.createCounterboreInput(vi(3.4), vi(6.5), vi(3.2))   # M3 SHCS
# hi = hf.createCountersinkInput(vi(3.4), vi(6.6), vi(90, 'deg'))
# hi = hf.createSimpleInput(vi(2.5))
hi.setPositionBySketchPoints(pts)
hi.setDistanceExtent(vi(8))                    # or hi.setAllExtent(af.ExtentDirections.PositiveExtentDirection)
holes = hf.add(hi)
```
Hole direction is into the body from the sketch face (no '-' needed, unlike extrude).

## Modeled thread on a cylinder
```python
cyl = faces(b, kind='cyl')[0]
q = af.ThreadDataQuery.create(False)
ttype = q.defaultMetricThreadType               # 'ISO Metric profile'
ok, desig, cls = q.recommendThreadData(cyl.geometry.radius * 2, False, ttype)  # cm diameter; False = external
info = af.ThreadInfo.create(False, False, ttype, desig, cls, True)
ti = c.features.threadFeatures.createInput(coll(cyl), info)
ti.isFullLength = True
ti.isModeled = True                              # real geometry (for 3D printing); False = cosmetic
c.features.threadFeatures.add(ti)
```
Internal thread: second arg `True` in both calls, on the hole's cylindrical face.
List sizes: `q.allSizes(ttype)`, `q.allDesignations(ttype, '6')`, `q.allClasses(False, ttype, 'M6x1')`.

## Split body (lid / base)
```python
cut_pl = plane(c, 'xy', offset=12)
sb = c.features.splitBodyFeatures
si = sb.createInput(b, cut_pl, True)              # True = extend the splitting tool
split = sb.add(si)                                # split.bodies -> both halves
```

## Construction planes
```python
cp = c.constructionPlanes
i = cp.createInput(); i.setByAngle(c.xConstructionAxis, vi(30, 'deg'), c.xYConstructionPlane); tilted = cp.add(i)
i = cp.createInput(); i.setByTwoPlanes(face_a, face_b); mid = cp.add(i)
i = cp.createInput(); i.setByPath(path, af.PathDistanceTypes.ProportionalPathDistanceType, vi(0.5, 'n')); normal_mid = cp.add(i)
```

## Body -> component, joints, grounding
```python
new_comp = b.createComponent().parentComponent   # body moves into a new component
occ = root().allOccurrencesByComponent(new_comp).item(0)   # (defined on BaseComponent)
new_comp.name = 'Lid'
occ.isGrounded = True
# Rigid/revolute joint between two occurrences using circular edges (proxies!):
e1 = edges(occA.bRepBodies.item(0), kind='circle')[0]
e2 = edges(occB.bRepBodies.item(0), kind='circle')[0]
g1 = af.JointGeometry.createByCurve(e1, af.JointKeyPointTypes.CenterKeyPoint)
g2 = af.JointGeometry.createByCurve(e2, af.JointKeyPointTypes.CenterKeyPoint)
ji = root().joints.createInput(g2, g1)           # FIRST = the part that moves (occB), second = fixed
ji.setAsRevoluteJointMotion(af.JointDirections.ZAxisJointDirection)
joint = root().joints.add(ji)                    # occB snaps onto occA's edge centre
```
Face-on-face (e.g. a cap seated on a recess floor with `createByPlanarFace`): set
`ji.isFlipped = True` before `add` so the faces mate instead of aligning normals, then assert the
moved part's `boundingBox.minPoint.z`.
Joints/as-built joints live in the parent (usually root) and need occurrence-context
entities: take bodies/edges from `occ.bRepBodies`, not from `occ.component.bRepBodies`.
Keep the current position: `root().asBuiltJoints.createInput(occA, occB, g1)`.

## Draft / offset faces
```python
side = faces(b, kind='plane', where=lambda f: abs(mm(f.pointOnFace)[2] - 5) < 4.9 and
             abs(f.evaluator.getNormalAtPoint(f.pointOnFace)[1].z) < 1e-6)
di = c.features.draftFeatures.createInput(side, face_end(b, 'z', 'min'), True)
di.setSingleAngle(False, vi(2, 'deg'))
c.features.draftFeatures.add(di)
oi = c.features.offsetFacesFeatures.createInput([face_end(b, 'z', 'max')], vi(-0.4))
c.features.offsetFacesFeatures.add(oi)            # press-pull style face offset
```
