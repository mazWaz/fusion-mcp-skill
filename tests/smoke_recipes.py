scratch('smoke_recipes')
c = root()
param('box_w', 40); param('box_d', 25); param('hole_d', 3.2)

# --- parametric sketch
sk = sketch(c, 'xy', 'plate_dims')
lines = crect(sk, 40, 25)
dims, gc = sk.sketchDimensions, sk.geometricConstraints
gc.addHorizontal(lines[0]); gc.addHorizontal(lines[2]); gc.addVertical(lines[1]); gc.addVertical(lines[3])
H = af.DimensionOrientations.HorizontalDimensionOrientation
V_ = af.DimensionOrientations.VerticalDimensionOrientation
dw = dims.addDistanceDimension(lines[0].startSketchPoint, lines[0].endSketchPoint, H, P(0, -16))
dh = dims.addDistanceDimension(lines[1].startSketchPoint, lines[1].endSketchPoint, V_, P(24, 0))
dw.parameter.expression = 'box_w'
dh.parameter.expression = 'box_d'
hole = circle(sk, 3.2, 15, 8)
dims.addDiameterDimension(hole, P(18, 11)).parameter.expression = 'hole_d'
print('1 sketch dims ok, fully constrained:', sk.isFullyConstrained)
b = extrude(c, prof(sk, 'largest'), 10, name='Block').bodies.item(0)

# --- loft
s0 = sketch(c, 'xy', 'loft0', offset=20); crect(s0, 30, 30, 60, 0)
s1 = sketch(c, 'xy', 'loft1', offset=40); circle(s1, 16, 60, 0)
lf = c.features.loftFeatures
li = lf.createInput(OPS['new'])
li.loftSections.add(prof(s0)); li.loftSections.add(prof(s1))
li.isSolid = True
loft = lf.add(li)
print('2 loft ok', loft.bodies.item(0).isSolid)

# --- sweep + pipe
path_sk = sketch(c, 'xz', 'path')
pl = poly(path_sk, [(-60, 0), (-60, -20), (-45, -30)], closed=False)
path = af.Path.create(coll(pl), af.ChainedCurveOptions.connectedChainedCurves)
prof_sk = sketch(c, 'xy', 'sweep_prof'); circle(prof_sk, 4, -60, 0)
sw = c.features.sweepFeatures
si = sw.createInput(prof(prof_sk), path, OPS['new'])
si.orientation = af.SweepOrientationTypes.PerpendicularOrientationType
sweep = sw.add(si)
print('3 sweep ok', sweep.bodies.count)
path_sk2 = sketch(c, 'xz', 'path2')
pl2 = poly(path_sk2, [(-80, 0), (-80, -20), (-65, -30)], closed=False)
path2 = af.Path.create(coll(pl2), af.ChainedCurveOptions.connectedChainedCurves)
pi = c.features.pipeFeatures.createInput(path2, OPS['new'])
pi.sectionSize = vi(3); pi.isHollow = True; pi.sectionThickness = vi(0.5)
pipe = c.features.pipeFeatures.add(pi)
print('3b pipe ok', pipe.bodies.count)

# --- hole feature (counterbore)
hs = sketch(c, face_end(b, 'z', 'max'), 'hole_pts')
pts = coll([hs.sketchPoints.add(P(*sp(hs, x, y))) for x, y in [(-15, -8), (-5, 8)]])
hf = c.features.holeFeatures
hi = hf.createCounterboreInput(vi(3.4), vi(6.5), vi(3.2))
hi.setPositionBySketchPoints(pts)
hi.setDistanceExtent(vi(8))
holes = hf.add(hi)
cyl_z = sorted(set(round(mm(f.boundingBox.minPoint)[2], 1) for f in holes.faces if f.geometry.surfaceType == ac.SurfaceTypes.CylinderSurfaceType))
print('4 hole ok, cyl face min z', cyl_z, '(body top z=10 -> into body if < 10)')

# --- thread on a pin
ps = sketch(c, face_end(b, 'z', 'max'), 'pin')
circle(ps, 6, *sp(ps, 10, -5))
pin = extrude(c, prof_at(ps, *sp(ps, 10, -5)), 8, op='join', name='Pin')
cyl = [f for f in pin.sideFaces if f.geometry.surfaceType == ac.SurfaceTypes.CylinderSurfaceType][0]
q = af.ThreadDataQuery.create(False)
ttype = q.defaultMetricThreadType
ok, desig, cls = q.recommendThreadData(cyl.geometry.radius * 2, False, ttype)
info = af.ThreadInfo.create(False, False, ttype, desig, cls, True)
ti = c.features.threadFeatures.createInput(coll(cyl), info)
ti.isFullLength = True
ti.isModeled = True
th = c.features.threadFeatures.add(ti)
print('5 thread ok', ttype, desig, cls)

# --- split body
sb = c.features.splitBodyFeatures
spl = sb.createInput(loft.bodies.item(0), plane(c, 'xy', offset=30), True)
split = sb.add(spl)
print('6 split ok, bodies', split.bodies.count)

# --- construction planes
cp = c.constructionPlanes
i = cp.createInput(); i.setByAngle(c.xConstructionAxis, vi(30, 'deg'), c.xYConstructionPlane); tilted = cp.add(i)
i = cp.createInput(); i.setByTwoPlanes(face_end(b, 'z', 'min'), plane(c, 'xy', offset=10)); mid = cp.add(i)
i = cp.createInput(); i.setByPath(path, af.PathDistanceTypes.ProportionalPathDistanceType, vi(0.5, 'n')); normal_mid = cp.add(i)
print('7 planes ok', tilted.name, mid.name, normal_mid.name)

# --- draft + offset faces on a fresh block
ds = sketch(c, 'xy', 'draft_blk'); crect(ds, 20, 20, 0, 45)
db = extrude(c, prof(ds), 10, name='DraftBlock').bodies.item(0)
side = faces(db, kind='plane', where=lambda f: abs(f.evaluator.getNormalAtPoint(f.pointOnFace)[1].z) < 1e-6)
di = c.features.draftFeatures.createInput(side, face_end(db, 'z', 'min'), True)
di.setSingleAngle(False, vi(2, 'deg'))
c.features.draftFeatures.add(di)
oi = c.features.offsetFacesFeatures.createInput([face_end(db, 'z', 'max')], vi(-0.4))
c.features.offsetFacesFeatures.add(oi)
print('8 draft+offset ok', fh._body_line(db, False))

# --- body -> component, joints
a_sk = sketch(c, 'xy', 'jA'); circle(a_sk, 10, 0, -45)
ba = extrude(c, prof(a_sk), 4, name='JA').bodies.item(0)
b_sk = sketch(c, 'xy', 'jB'); circle(b_sk, 6, 30, -45)
bb_ = extrude(c, prof(b_sk), 6, name='JB').bodies.item(0)
ca = ba.createComponent().parentComponent; cb = bb_.createComponent().parentComponent
occA = root().allOccurrencesByComponent(ca).item(0); occB = root().allOccurrencesByComponent(cb).item(0)
occA.component.name = 'Base'; occB.component.name = 'Knob'
occA.isGrounded = True
e1 = edges(occA.bRepBodies.item(0), kind='circle', where=lambda e: mm(e.pointOnEdge)[2] > 3.9)[0]
e2 = edges(occB.bRepBodies.item(0), kind='circle', where=lambda e: mm(e.pointOnEdge)[2] < 0.1)[0]
g1 = af.JointGeometry.createByCurve(e1, af.JointKeyPointTypes.CenterKeyPoint)
g2 = af.JointGeometry.createByCurve(e2, af.JointKeyPointTypes.CenterKeyPoint)
ji = root().joints.createInput(g2, g1)
ji.setAsRevoluteJointMotion(af.JointDirections.ZAxisJointDirection)
joint = root().joints.add(ji)
print('9 joint ok', joint.name, 'knob now at', mm(occB.bRepBodies.item(0).boundingBox.minPoint, 1))
report(phys=False)
