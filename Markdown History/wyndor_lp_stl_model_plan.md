# Wyndor LP 3D Print — STL Generation Plan

## You are on the right track

Yes — **Cursor can absolutely help you create STL files**. For a problem like this, the best workflow is:

1. **Compute the math** (feasible polygon + objective plane) in Python
2. **Build triangle meshes** for the solid body and accent features
3. **Export STL** (two files for two AMS filaments)
4. **Import into Bambu Studio**, assign colors, slice, print

A single STL *can* work, but for your AMS two-color setup, **two aligned STL files** (body + accents) is the cleanest path: import both, assign Filament 1 to the body and Filament 2 to the ridges, then print.

Your reference photo ([IMG_8086.HEIC](IMG_8086.HEIC)) matches the classic textbook style: a **solid prism** whose footprint is the feasible region, whose **top is the objective function surface** (a sloped plane), with **constraint boundaries emphasized on the vertical sides** and **iso-profit contour lines** etched/raised on the top.

---

## Problem data (from [Wyndor_Formulation.pdf](Wyndor_Formulation.pdf))

**Maximize:** `Z = 300·x₁ + 500·x₂`

**Constraints:**

| Constraint | Boundary line |
|---|---|
| x₁ ≤ 4 | x₁ = 4 |
| 2x₂ ≤ 12 → x₂ ≤ 6 | x₂ = 6 |
| 3x₁ + 2x₂ ≤ 18 | 3x₁ + 2x₂ = 18 |
| x₁ ≥ 0, x₂ ≥ 0 | axes |

**Feasible region vertices** (counterclockwise):

```text
(0,0) → (4,0) → (4,3) → (2,6) → (0,6)
```

**Objective at corners:** Z = 0, 1200, 2700, **3600** (optimum at (2,6)), 3000

---

## Physical scaling (small desk model, ~80–100 mm)

| Axis | Real range | Target print size |
|---|---|---|
| x₁ | 0–4 | maps to ~60 mm |
| x₂ | 0–6 | maps to ~90 mm (dominant width) |
| Z (profit) | 0–3600 | maps to ~25–30 mm height |

Constants at the top of the script (easy for you to tweak):

- `SCALE_XY = 15.0`  → 1 LP unit = 15 mm (gives 60×90 mm footprint)
- `Z_SCALE = 30.0 / 3600` → max height ≈ 30 mm
- `RIDGE_WIDTH = 1.0` mm, `RIDGE_HEIGHT = 0.5` mm (accent strips)

---

## Mesh design — two STL parts

### Part 1: `wyndor_body.stl` (Filament 1 — main color)

A **closed, manifold solid**:

- **Bottom face:** pentagon triangulated at z = 0
- **Top face:** same pentagon, each vertex lifted to `z = Z(x₁, x₂)`
- **Side walls:** 5 vertical quads connecting bottom ↔ top along each constraint boundary

### Part 2: `wyndor_accents.stl` (Filament 2 — contrast color)

Thin raised geometry (separate mesh, same XY alignment):

1. **Side boundary ridges** — along all 5 feasible-region edges
2. **Top contour ridges** — iso-profit lines at Z = 600, 1200, 1800, 2400, 3000, 3600

---

## Implementation approach

```text
3D Printing/
  Markdown History/
  wyndor_print/
    requirements.txt
    generate_wyndor_stl.py
    output/
      wyndor_body.stl
      wyndor_accents.stl
```
