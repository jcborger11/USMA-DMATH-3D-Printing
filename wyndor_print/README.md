# Wyndor LP 3D Print

Generates a single STL for a one-filament print of the Wyndor Glass Co. linear programming problem:

- **wyndor_body.stl** — solid feasible region with sloped objective-function top, plus engraved cavities for iso-profit grooves, objective labels, and side-wall constraint labels

Features are **inset into the body** so they read as engraved detail in a single filament (no accent STL required).

Set `BODY_ONLY = False` in `generate_wyndor_stl.py` to also export `wyndor_accents.stl` for two-color AMS inlays.

## Generate STL

```bash
cd wyndor_print && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python generate_wyndor_stl.py
```

Output: `output/wyndor_body.stl`

Running the generator also opens a **rotatable pyglet preview** of the body. Use `--no-preview` to skip it.

## Preview (without Bambu Studio)

```bash
cd wyndor_print && .venv/bin/python preview.py
```

Writes `output/preview.png` (three views: isometric, front, side). Shows **wyndor_body.stl** only by default.

Interactive rotatable window:

```bash
cd wyndor_print && .venv/bin/pip install "pyglet<2" && .venv/bin/python preview.py --interactive
```

## Input

Reference materials in `input/`:

- **Wyndor_Formulation.pdf** — LP problem statement
- **example sketch.HEIC** — reference photo (local only; ignored by git)

## Tweak settings

Edit the constants at the top of `generate_wyndor_stl.py`:

| Constant | Default | Purpose |
|---|---|---|
| `BODY_ONLY` | True | Export body STL only; skip accent fills |
| `SCALE_XY` | 15.0 | LP units → mm (footprint ≈ 60 × 90 mm) |
| `MAX_Z_MM` | 30.0 | Max model height in mm |
| `RIDGE_WIDTH` | 1.0 | Iso-profit groove width (mm) |
| `GROOVE_DEPTH` | 0.5 | Depth contour channels are cut into the top surface (mm) |
| `LABEL_INSET_DEPTH` | 0.5 | Depth side-wall text cavities extend into body (mm) |
| `CONTOUR_LABEL_FONT_SIZE` | 8.0 | Top objective equation font size |
| `CONTOUR_LABEL_INSET_DEPTH` | 0.8 | Depth top equation cavities extend into body (mm) |
| `CONTOUR_LABEL_MAX_HEIGHT_MM` | 3.7 | Max height for fitted top equation text (mm) |
| `CONTOUR_LABEL_GAP_MM` | 1.5 | Clearance between groove edge and equation text (mm) |
| `INSET_CLEARANCE` | 0.05 | Extra cutter depth/width for two-color inlay mode (mm) |
| `WALL_LABEL_OVERRIDES` | see script | Per-edge placement tweaks (`x₁ ≥ 0`, `x₂ ≥ 0`, etc.) |
| `CONTOUR_LEVELS` | 1200, 2000, 2700 | Iso-profit lines on the top surface |

## Bambu Studio workflow

1. **File → Import** `output/wyndor_body.stl`.
2. Slice with your usual profile (0.2 mm layers work well at this size).
3. Engraved grooves and labels show as inset detail in the single filament.

## LP reference

Maximize `Z = 300·x₁ + 500·x₂` subject to `x₁ ≤ 4`, `x₂ ≤ 6`, `3x₁ + 2x₂ ≤ 18`, `x₁, x₂ ≥ 0`.

Feasible region vertices: (0,0) → (4,0) → (4,3) → (2,6) → (0,6). Optimum Z = 3600 at (2, 6).
