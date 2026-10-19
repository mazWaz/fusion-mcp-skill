# fusion-mcp skill

A Claude Code skill for driving **Autodesk Fusion** through its local MCP server
(`http://127.0.0.1:27182/mcp`, Preferences > General > API > Fusion MCP Server).

- **Token-efficient generation**: `scripts/fh.py` helpers (mm / degrees / parameter
  expressions, fully-constrained parametric sketches, features, selection, export) keep
  MCP scripts to a few lines; long models live in re-runnable files executed with `run_file()`.
- **Detailed results**: workflow + quality checklist (user parameters, named features,
  components, materials, numeric verification with `report()`).
- **Complete API coverage**: a grep-able reference of every Fusion API class, member and enum
  (core, fusion, cam, drawing, electron, sim, volume) generated from Fusion's own type stubs.
- **Verified gotchas & recipes**: error text -> cause -> fix, and tested raw-API recipes
  (loft, sweep/pipe, holes, threads, split, construction planes, joints, draft).

## Install

```bash
git clone <this repo> ~/.claude/skills/fusion-mcp
python -I ~/.claude/skills/fusion-mcp/scripts/build_api_ref.py   # builds api/ (needs Fusion installed)
```

Re-run `build_api_ref.py` after every Fusion update. Claude Code picks the skill up
automatically for any Fusion work.

## Layout

| Path | Purpose |
|---|---|
| `SKILL.md` | Workflow, helper quick reference, API lookup, output economy, quality checklist |
| `scripts/fh.py` | Helper library imported by every MCP script |
| `scripts/build_api_ref.py` | Generates `api/` (`classes.txt`, `members.txt`, `ref/<ns>/<Class>.md`) |
| `reference/gotchas.md` | Symptom / error text -> cause -> fix |
| `reference/recipes.md` | Tested raw-API recipes beyond the helpers |
| `tests/smoke_*.py` | Smoke tests run inside Fusion (see below) |

## Smoke tests

Each test opens (or re-uses) its own tagged scratch design and never touches other documents.
Run through `fusion_mcp_execute` (`featureType: script`):

```python
import sys, os, importlib; sys.path.insert(0, os.path.expanduser('~/.claude/skills/fusion-mcp/scripts'))
import fh; importlib.reload(fh); from fh import *

def run(_context: str):
    t = os.path.expanduser('~/.claude/skills/fusion-mcp/tests')
    for name in ['smoke_helpers', 'smoke_recipes', 'smoke_parametric']:
        run_file(os.path.join(t, name + '.py'), OUT=os.path.join(t, 'out'))
```

Every test ends with `report()`; expect `timeline ... OK` and no traceback.
Verified against Fusion 2705.1.30 (Python 3.14).
