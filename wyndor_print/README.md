# Wyndor LP 3D Print

Generates two aligned STL files for a two-color AMS print of the Wyndor Glass Co. linear programming problem:

- **wyndor_body.stl** — solid feasible region with sloped objective-function top, plus cavities cut for inlays (Filament 1)
- **wyndor_accents.stl** — inlay fills for iso-profit grooves, objective labels, and side-wall constraint labels (Filament 2)

Accent geometry is **inset into the body** (not raised on top), so FDM layers have solid support underneath every label and groove.

## Generate STLs

```bash
cd wyndor_print && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python generate_wyndor_stl.py
```

Output files are written to `output/`.

## Preview (without Bambu Studio)

```bash
cd wyndor_print && .venv/bin/python preview.py
```

Writes `output/preview.png` (three views: isometric, front, side).

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
| `SCALE_XY` | 15.0 | LP units → mm (footprint ≈ 60 × 90 mm) |
| `MAX_Z_MM` | 30.0 | Max model height in mm |
| `RIDGE_WIDTH` | 1.0 | Iso-profit groove width (mm) |
| `GROOVE_DEPTH` | 0.5 | Depth contour channels are cut into the top surface (mm) |
| `LABEL_INSET_DEPTH` | 0.5 | Depth text cavities extend into body walls and top (mm) |
| `INSET_CLEARANCE` | 0.05 | Extra cutter depth/width so accent fills seat cleanly (mm) |
| `CONTOUR_LEVELS` | 1200, 2000, 2700 | Iso-profit lines on the top surface |

## Bambu Studio workflow

1. **File → Import** both `output/wyndor_body.stl` and `output/wyndor_accents.stl`.
2. Confirm they align on the build plate (same origin and scale).
3. If both shells import as one object: right-click → **Split → To Parts** (not “To Objects”).
4. In the object list, assign **Filament 1** to the body and **Filament 2** to the accents.
5. Slice with your usual profile (0.2 mm layers work well at this size).
6. Optional: enable **Flush into infill** to reduce purge waste between color changes.

## LP reference

Maximize `Z = 300·x₁ + 500·x₂` subject to `x₁ ≤ 4`, `x₂ ≤ 6`, `3x₁ + 2x₂ ≤ 18`, `x₁, x₂ ≥ 0`.

Feasible region vertices: (0,0) → (4,0) → (4,3) → (2,6) → (0,6). Optimum Z = 3600 at (2, 6).
