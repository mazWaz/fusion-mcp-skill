scratch('smoke_threads')
# Printed-thread workflow: cross-component cuts (only=), thread clearance, lead-in, phase fit check.
# Stud bodies live in component Studs, nut bodies in Nuts, all axes vertical.
S, N = comp('Studs'), comp('Nuts')


def cyl(b, d):
    return faces(b, kind='cyl', where=lambda f: abs(f.geometry.radius * 20 - d) < 0.01)[0]


def body_at(c, d, h, x, z0=0, name=None):
    sk = sketch(c, 'xy', None, offset=z0 or None)
    circle(sk, d, x, 0)
    b = extrude(c, prof(sk), h).bodies.item(0)
    b.name = name or b.name
    return b


def bore(c, x, depth, only):
    sk = sketch(c, 'xy')
    circle(sk, 6.8, x, 0)
    return extrude(c, prof(sk), depth, 'cut', only=only)


# --- 1 cross-component cut: a plain cut also hollows the stud of the other component
stud1 = body_at(S, 8, 10, 0, name='stud1')
nut1 = body_at(N, 16, 8, 0, name='nut1')
v0 = stud1.volume
naive = bore(N, 0, 8, None)
hit = abs(stud1.volume - v0) > 1e-6
naive.deleteMe()
bore(N, 0, 8, [nut1])
print('1 plain cut hit other component:', hit, '| only= keeps it:', abs(stud1.volume - v0) < 1e-6)

# --- 2 clearance threads, full engagement -> free rotation window
thread(S, cyl(stud1, 8), 'M8x1.25', clr=0.1, name='stud1 thread')
thread(N, cyl(nut1, 6.8), 'M8x1.25', internal=True, clr=0.1, name='nut1 thread')
print('2 fit with clearance (max, min, free deg, play mm):',
      [round(v, 3) for v in thread_fit(nut1, stud1, 1.25, step=5)])

# --- 3 chamfer BEFORE thread: unthreaded tip cone jams in the blind socket (min overlap > 0)
stud2 = body_at(S, 8, 6, 30, name='stud2')
chamfer(S, edges([face_end(stud2, 'z', 'max')]), 1)
nut2 = body_at(N, 16, 10, 30, name='nut2')
bore(N, 30, 8, [nut2])
thread(S, cyl(stud2, 8), 'M8x1.25')                    # clr here fails: ASM_BL_CAP_COMPLEX
thread(N, cyl(nut2, 6.8), 'M8x1.25', internal=True, clr=0.2)
f3 = thread_fit(nut2, stud2, 1.25, step=5, center=(30, 0))
print('3 chamfer-then-thread min overlap mm3:', round(f3[1], 3), '(jams)' if f3[1] > 1e-3 else '(free?)')

# --- 4 thread FIRST, then 45 deg lead-in revolved through the teeth (only= the stud) -> free
stud3 = body_at(S, 8, 6, 60, name='stud3')
nut3 = body_at(N, 16, 10, 60, name='nut3')
bore(N, 60, 8, [nut3])
thread(S, cyl(stud3, 8), 'M8x1.25', clr=0.1)
thread(N, cyl(nut3, 6.8), 'M8x1.25', internal=True, clr=0.1)
sk = sketch(S, 'xz', 'lead-in')
r0, h = 3.0, 1.3
poly(sk, [sp(sk, 60 + r0 - 0.5, 0, 6.5), sp(sk, 60 + r0 + h + 0.5, 0, 6 - h - 0.5), sp(sk, 60 + r0 + h + 0.5, 0, 6.5)])
ax = sk.sketchCurves.sketchLines.addByTwoPoints(P(*sp(sk, 60, 0, 0)), P(*sp(sk, 60, 0, 7)))
ax.isConstruction = True
revolve(S, prof(sk), ax, op='cut', only=[stud3])
f4 = thread_fit(nut3, stud3, 1.25, step=5, center=(60, 0))
print('4 thread-then-lead-in min overlap mm3:', round(f4[1], 3), 'free deg', f4[2], 'nut3 intact:',
      nut3.volume > 0 and N.bRepBodies.count == 3)
report(phys=False)
