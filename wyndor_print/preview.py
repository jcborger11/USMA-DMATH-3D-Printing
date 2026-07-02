#!/usr/bin/env python3
"""Preview wyndor_body.stl (and optionally wyndor_accents.stl)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"
BODY_COLOR = (0.78, 0.78, 0.82, 1.0)
ACCENT_COLOR = (0.78, 0.28, 0.28, 1.0)


def load_meshes(body_only: bool) -> tuple[trimesh.Trimesh, trimesh.Trimesh | None]:
    body_path = OUTPUT_DIR / "wyndor_body.stl"
    accents_path = OUTPUT_DIR / "wyndor_accents.stl"
    if not body_path.exists():
        raise FileNotFoundError(
            f"Body STL not found at {body_path}. Run generate_wyndor_stl.py first."
        )
    body = trimesh.load(body_path)
    if body_only or not accents_path.exists():
        return body, None
    return body, trimesh.load(accents_path)


def add_mesh_to_axes(
    ax: plt.Axes,
    mesh: trimesh.Trimesh,
    facecolor: tuple[float, float, float, float],
) -> None:
    triangles = mesh.vertices[mesh.faces]
    collection = Poly3DCollection(
        triangles,
        facecolors=facecolor,
        edgecolors=(0.15, 0.15, 0.15, 0.35),
        linewidths=0.2,
    )
    ax.add_collection3d(collection)


def set_equal_axes(ax: plt.Axes, vertices: np.ndarray) -> None:
    mins = vertices.min(axis=0)
    maxs = vertices.max(axis=0)
    center = (mins + maxs) / 2.0
    radius = (maxs - mins).max() / 2.0
    for setter, value in zip(
        (ax.set_xlim, ax.set_ylim, ax.set_zlim),
        (center[0], center[1], center[2]),
    ):
        setter(value - radius, value + radius)


def save_png(
    body: trimesh.Trimesh,
    accents: trimesh.Trimesh | None,
    path: Path,
) -> None:
    meshes = [body.vertices]
    if accents is not None:
        meshes.append(accents.vertices)
    all_vertices = np.vstack(meshes)
    views = [
        ("isometric", 25, 45),
        ("front", 10, 0),
        ("side", 10, 90),
    ]

    title = "Wyndor LP model — body only" if accents is None else "Wyndor LP model — gray body, red accents"
    fig = plt.figure(figsize=(14, 5))
    for index, (view_title, elev, azim) in enumerate(views, start=1):
        ax = fig.add_subplot(1, 3, index, projection="3d")
        add_mesh_to_axes(ax, body, BODY_COLOR)
        if accents is not None:
            add_mesh_to_axes(ax, accents, ACCENT_COLOR)
        set_equal_axes(ax, all_vertices)
        ax.view_init(elev=elev, azim=azim)
        ax.set_title(view_title)
        ax.set_xlabel("X (mm)")
        ax.set_ylabel("Y (mm)")
        ax.set_zlabel("Z (mm)")

    fig.suptitle(title, fontsize=13)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def show_interactive(body: trimesh.Trimesh, accents: trimesh.Trimesh | None) -> None:
    try:
        body_copy = body.copy()
        body_copy.visual.face_colors = [200, 200, 210, 255]
        meshes = [body_copy]
        if accents is not None:
            accents_copy = accents.copy()
            accents_copy.visual.face_colors = [200, 70, 70, 255]
            meshes.append(accents_copy)
        scene = trimesh.Scene(meshes)
        scene.show(caption="Wyndor LP — drag to rotate, scroll to zoom")
    except ImportError as exc:
        raise SystemExit(
            "Interactive preview needs pyglet 1.x. Install with:\n"
            '  .venv/bin/pip install "pyglet<2"\n'
            f"Original error: {exc}"
        ) from exc


def regenerate_stls() -> None:
    subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "generate_wyndor_stl.py"), "--no-preview"],
        check=True,
        cwd=SCRIPT_DIR,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview Wyndor LP STL files.")
    parser.add_argument(
        "--no-regenerate",
        action="store_true",
        help="Skip regenerating STLs before preview.",
    )
    parser.add_argument(
        "--with-accents",
        action="store_true",
        help="Also overlay wyndor_accents.stl (legacy two-color preview).",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Open interactive 3D window (requires pyglet).",
    )
    parser.add_argument(
        "--png",
        type=Path,
        default=OUTPUT_DIR / "preview.png",
        help="Path for PNG render (default: output/preview.png).",
    )
    args = parser.parse_args()

    if not args.no_regenerate:
        regenerate_stls()

    body_only = not args.with_accents
    body, accents = load_meshes(body_only)
    args.png.parent.mkdir(parents=True, exist_ok=True)
    save_png(body, accents, args.png)
    print(f"Saved preview image: {args.png}")

    if args.interactive:
        show_interactive(body, accents)


if __name__ == "__main__":
    main()
