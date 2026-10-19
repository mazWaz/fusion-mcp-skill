# Fusion API / MCP gotchas (symptom -> cause -> fix)

| Symptom / error text | Cause | Fix |
|---|---|---|
| `Design.cast(app.activeProduct)` is None; objectType `adsk::electron::EcadDesign`, `adsk::drawing::...`, `adsk::cam::CAM` | Active document/workspace is Electronics, Drawing or Manufacture | `new_design()` (new doc) or activate a design doc; never repurpose the user's doc |
| `3 : param name is not valid` | Name equals a unit symbol (`mm cm m in ft deg rad r ...`) or already exists | Descriptive names (`box_w`, `wall_t`, `fil_r`); `param()` updates existing ones |
| `Could not complete Through All Extrude, body not found` / cut does nothing | Sketch on a body face: + direction = outward face normal, so the cut goes into air | Use `-dist` / `'-all'` / `'all-both'` for cuts from face sketches |
| Extrude of `profs(face_sketch)` thickens the whole body | Face sketches auto-project the face outline -> extra outline profile | Pick with `prof_at(sk, x, y)` / `prof(sk,'smallest')`; or sketch on `plane(c,'xy',offset=z)` |
| `face_end(b,'z','max')` returns the wrong face later in the script | Top face changes after bosses/text/pins are added | Grab faces right after the feature that makes them, or use offset construction planes |
| Geometry appears at -Z or mirrored on XZ / YZ sketches | XZ sketch (x,y) -> model (x, 0, -y); YZ sketch (x,y) -> model (0, y, -x) | Convert with `sp(sk, x, y, z)` (model mm -> sketch mm) |
| `createInput3 ... invalid expression` (text) | Sketch text is an expression; plain text needs quotes | `fh.text()` quotes it; `expr=True` for `"'V' + ver"` |
| Text is not extruded / missing | `SketchText` is not in `sketch.profiles` | Extrude the `SketchText` object returned by `text()` |
| Through-all cut goes the wrong way (raw API) | `setOneSideExtent(..., NegativeExtentDirection)` is ignored for through-all | Set `ThroughAllExtentDefinition.isPositiveDirection` (fh `'-all'` does); verify which wall was cut |
| `RuntimeError: 3 : invalid name` / `failed to find product` from `itemByName` / `itemByProductType` | Many `itemBy*` lookups raise instead of returning None | Wrap in try/except (`fh._by_name`) or loop and compare names |
| Failed script left half a model behind | No rollback: features created before the exception stay | Re-runnable model files starting with `scratch()`; in user docs, `fusion_mcp_update` undo per feature |
| `isFullyConstrained` False after `rect`/`crect` | `addTwoPointRectangle` / `addCenterPointRectangle` add no H/V constraints | `gc.addHorizontal(l)` / `addVertical(l)` on the 4 lines (see recipes) |
| `VCS_SKETCH_OVER_CONSTRAINTS` when dimensioning several circle centres from `sketch.originPoint` | Solver rejects repeated origin->centre dims once centres share an x or y (reproducible, any plane) | `pcrect(sk, w, h, construction=True)` + `pcircles(sk, corners, d)`; or dimension centre-to-centre; single circle: `pcircle()` |
| `root component name cannot be changed` | Root component takes the document name | Name sub-components / bodies / features instead |
| `itemByName('Pilots')` is None; feature shows as `Pilots (1)` | Timeline names are unique across sketches *and* features | Distinct names (`'Pilot Circles'` sketch, `'Pilots'` feature); fh prints a note on rename |
| Extrude from an XZ / YZ sketch goes the "wrong" way | XZ sketch normal = +Y, YZ sketch normal = +X | `+dist` / `'all'` goes +Y (+X); `'-all'` / `rev=True` goes -Y (-X) |
| Values 10x off | API uses cm (lengths) and radians (angles); `ValueInput.createByReal` is cm | `vi(mm)` / `P(mm)` helpers; or `createByString('12 mm')`; `report()` prints mm |
| Script refuses to run: command dialog open | Modifying scripts cannot run while a Fusion command dialog is open | Ask user to close it; inspection works with `readOnly: true` |
| `readOnly` script fails "Cannot modify the design from a read-only context" | Read-only is enforced (also blocks `executeTextCommand`) | Drop `readOnly` for scripts that create/modify |
| Error has no line info / silent failure | Exception caught inside `run` | Never wrap `run` in try/except; the MCP returns the full traceback |
| Edited `fh.py` / model file has no effect | Fusion's interpreter caches modules | Prelude reloads fh; `run_file()` re-reads the file every call |
| Feature exists but geometry is wrong / red in timeline | Feature computed with warnings/errors | `report()` / `health()` after every stage; read `errorOrWarningMessage` |
| `Fillet could not be computed` | Radius >= wall/edge length, or fillet after shell on thin walls | Fillet vertical outer edges before `shell`; keep radius < wall after shell |
| Mass looks like steel | Default material is Steel | `material(body, 'ABS Plastic')` / `'PLA'` / `'Aluminum'` |
| Screenshot shows a tiny model | Screenshot does not zoom | `fit()` in the preceding script; hide others with `isLightBulbOn = False` |
| Member not found in `members.txt` for a class | It is defined on a base class (e.g. `Design.attributes` lives on `core.Product`) | Check the base in `classes.txt` and grep the base class |
| Joint/edge from a sub-component behaves oddly or `invalid argument` | Using native entities where assembly-context proxies are required | Take bodies/edges from `occ.bRepBodies` (proxies) or `entity.createForAssemblyContext(occ)` |
| Features land in the wrong component | Features are created by the component whose `features` collection you call | Call `extrude(comp, ...)` with the component that owns the sketch/body |
| Re-running a model script duplicates features | Script appends to the existing timeline | Start model files with `scratch('<unique_tag>')` (only empties the never-saved doc created with that tag) |
| Two open docs both called "Untitled" | New docs share the default name | Identify docs by the fh scratch attribute / `app().activeDocument`, not by name |
| Cut by an expression goes the wrong side | `extrude` flips only for negative *numbers* | `rev=True` with expressions (`extrude(c, p, 'pilot_depth', 'cut', rev=True)`) |
| Parameters linger after `reset()` | Timeline delete keeps user parameters | Fine: `param()` updates them; delete via `design().userParameters.itemByName(n).deleteMe()` |
| Hole feature goes the wrong way | Unlike extrude, holes default into the body | `hi.isDefaultDirection = False` to flip |
| `invlid argument geometry` exporting STEP/IGES/SAT | CAD exporters accept a Component only (not body, not occurrence) | `export(occ)` maps to `occ.component`; bodies -> STL/3MF/OBJ |
| Joined part sits upside down / inside the other (face-to-face joint) | API aligns the two face normals instead of mating them like the Joint dialog | Set `JointInput.isFlipped = True` before `joints.add`, then check the moved part's min z; `Joint.isFlipped` afterwards raises `Cannot be edited before rolling back` |
| `First component to move is grounded, it can not move.` | `joints.createInput(g1, g2)`: g1's occurrence moves onto g2 | Put the moving part's geometry first |
| `createComponent().assemblyContext` is None | Returned body is native | `occ = root().allOccurrencesByComponent(body.parentComponent).item(0)` |
| Second body `Name (1)` appears / another component's body is hollowed or split by a cut | Cut / intersect participant bodies default to every body the tool touches, in any component | `extrude(..., 'cut', only=[body])`, `revolve(..., only=[body])`; raw API: `input.participantBodies = [body]` |
| Mating modeled threads report overlap (interference / boolean) although clearance was added | Static overlap depends on helix phase (rotation), not on fit | `thread_fit(fixed, moving, pitch)`: free_deg > 0 means it screws; free_deg x pitch / 360 = axial play |
| Screwed part jams: overlap at every rotation, located at the stud tip | A chamfer made *before* the modeled thread stays an unthreaded cone wider than the socket's minor diameter | Thread the full cylinder first, then revolve-cut a 45 deg lead-in through the teeth (`only=` the stud); socket mouth: counterbore (major + 0.6) x 0.8 instead of a chamfer (recipes) |
| `OffsetFaces2 / Compute Failed // ASM_BL_CAP_COMPLEX` adding thread clearance | Offsetting thread faces that run into a chamfer | Same fix (thread before lead-in), or put all the clearance on the mating part |
| `threadFeature.faces` is empty | After an offset-faces feature consumes them, the faces belong to the offset feature | Read `tf.faces` right after `threadFeatures.add` (`fh.thread(clr=...)` does) |
