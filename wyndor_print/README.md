# Wyndor LP 3D Print

Generates two aligned STL files for a two-color AMS print of the Wyndor Glass Co. linear programming problem:

- **wyndor_body.stl** — solid feasible region with sloped objective-function top (Filament 1)
- **wyndor_accents.stl** — boundary ridges on the sides and iso-profit contour lines on top (Filament 2)

## Preview (without Bambu Studio)

```bash
cd "/Users/johnb/Documents/Cursor Files/3D Printing/wyndor_print" && .venv/bin/python preview.py
```

Writes `output/preview.png` (three views: isometric, front, side).

Interactive rotatable window:

```bash
.venv/bin/pip install "pyglet<2" && .venv/bin/python preview.py --interactive
```


```bash
cd "/Users/johnb/Documents/Cursor Files/3D Printing/wyndor_print" && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python generate_wyndor_stl.py
```

Output files are written to `output/`.

## Tweak settings

Edit the constants at the top of `generate_wyndor_stl.py`:

| Constant | Default | Purpose |
|---|---|---|
| `SCALE_XY` | 15.0 | LP units → mm (footprint ≈ 60 × 90 mm) |
| `MAX_Z_MM` | 30.0 | Max model height in mm |
| `RIDGE_WIDTH` | 1.0 | Accent line thickness (mm) |
| `RIDGE_HEIGHT` | 0.5 | How far accents protrude (mm) |
| `CONTOUR_LEVELS` | 600 … 3600 | Iso-profit lines on the top surface |

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
