# USMA DMATH 3D Printing

Course materials for turning linear programming problems into printable 3D models.

## Projects

| Folder | Description |
|---|---|
| [`wyndor_print/`](wyndor_print/) | Wyndor Glass Co. LP model — dual-color STL generator (body + accents) |
| [`Markdown History/`](Markdown%20History/) | Archived planning notes |

## Reference

- [`wyndor_print/input/Wyndor_Formulation.pdf`](wyndor_print/input/Wyndor_Formulation.pdf) — LP problem statement

## Quick start

```bash
cd wyndor_print && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python generate_wyndor_stl.py
```

See [`wyndor_print/README.md`](wyndor_print/README.md) for preview, Bambu Studio workflow, and tweakable constants.
