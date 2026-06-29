#!/usr/bin/env python3
"""Generate STL meshes for the Wyndor Glass Co. LP 3D visualization."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import shapely.geometry
import trimesh
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath

# --- LP problem data ---
# Feasible region vertices (x1, x2), counterclockwise from above.
FEASIBLE_VERTICES = np.array(
    [
        [0.0, 0.0],
        [4.0, 0.0],
        [4.0, 3.0],
        [2.0, 6.0],
        [0.0, 6.0],
    ]
)

# Constraint label for each polygon edge (same order as vertices).
EDGE_CONSTRAINT_LABELS = [
    "x₂ ≥ 0",
    "x₁ ≤ 4",
    "3x₁ + 2x₂ ≤ 18",
    "x₂ ≤ 6",
    "x₁ ≥ 0",
]

# Maximize Z = 300*x1 + 500*x2
OBJ_A = 300.0
OBJ_B = 500.0
OBJECTIVE_LHS = "300x₁ + 500x₂"

# Iso-profit contour levels (profit units).
CONTOUR_LEVELS = [1200, 2000, 2700]

# --- Print scaling (millimeters) ---
SCALE_XY = 15.0  # 1 LP unit = 15 mm → 60 x 90 mm footprint
MAX_Z_MM = 30.0
Z_SCALE = MAX_Z_MM / 3600.0

# Accent geometry (millimeters).
RIDGE_WIDTH = 1.0
RIDGE_HEIGHT = 0.5
TEXT_FONT_SIZE = 6.0
TEXT_DEPTH = 0.5
LABEL_OFFSET_LP = 0.12  # offset below contour lines in LP units (~1.8 mm)
WALL_LABEL_V_FRACTION = 0.18  # vertical position: fraction up from base (not centered)
CONTOUR_LABEL_MAX_HEIGHT_MM = 2.8

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def objective(x1: float, x2: float) -> float:
    return OBJ_A * x1 + OBJ_B * x2


def scale_xy(x1: float, x2: float) -> tuple[float, float]:
    return x1 * SCALE_XY, x2 * SCALE_XY


def scale_z(z_profit: float) -> float:
    return z_profit * Z_SCALE


def to_mm(x1: float, x2: float, z_profit: float = 0.0) -> np.ndarray:
    x_mm, y_mm = scale_xy(x1, x2)
    z_mm = scale_z(z_profit)
    return np.array([x_mm, y_mm, z_mm], dtype=float)


def tri_fan_indices(n: int) -> np.ndarray:
    """Triangle fan from vertex 0 for a convex n-gon."""
    return np.array([[0, i, i + 1] for i in range(1, n - 1)], dtype=int)


def outward_normal_2d(p0: np.ndarray, p1: np.ndarray) -> np.ndarray:
    """Unit outward normal for a CCW polygon edge p0 -> p1."""
    edge = p1 - p0
    normal = np.array([edge[1], -edge[0]], dtype=float)
    length = np.linalg.norm(normal)
    if length < 1e-12:
        raise ValueError("Degenerate polygon edge.")
    return normal / length


def point_in_polygon(point: np.ndarray) -> bool:
    """Ray-casting test for a CCW polygon."""
    x, y = point
    inside = False
    verts = FEASIBLE_VERTICES
    n = len(verts)
    j = n - 1
    for i in range(n):
        xi, yi = verts[i]
        xj, yj = verts[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi
        ):
            inside = not inside
        j = i
    return inside


def make_transform(
    origin: np.ndarray,
    x_axis: np.ndarray,
    y_axis: np.ndarray,
    z_axis: np.ndarray,
) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, 0] = x_axis / np.linalg.norm(x_axis)
    matrix[:3, 1] = y_axis / np.linalg.norm(y_axis)
    matrix[:3, 2] = z_axis / np.linalg.norm(z_axis)
    matrix[:3, 3] = origin
    return matrix


def flip_text_180(
    x_axis: np.ndarray,
    y_axis: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Rotate label 180° in-plane so equations read right-side up."""
    return -x_axis, -y_axis


def create_text_mesh(text: str) -> trimesh.Trimesh:
    """Extrude matplotlib text glyphs into a 3D mesh (local XY plane, +Z depth)."""
    path = TextPath(
        (0, 0),
        text,
        prop=FontProperties(family="DejaVu Sans", size=TEXT_FONT_SIZE),
    )
    parts: list[trimesh.Trimesh] = []
    for poly in path.to_polygons():
        if len(poly) < 3:
            continue
        polygon = shapely.geometry.Polygon(poly)
        if polygon.area < 1e-8:
            continue
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        parts.append(trimesh.creation.extrude_polygon(polygon, height=TEXT_DEPTH))
    if not parts:
        raise ValueError(f"Could not generate text geometry for: {text!r}")
    mesh = trimesh.util.concatenate(parts)
    mesh.apply_translation(-mesh.centroid)
    return mesh


def fit_text_mesh(
    mesh: trimesh.Trimesh,
    max_width: float,
    max_height: float,
) -> trimesh.Trimesh:
    size = mesh.bounds[1] - mesh.bounds[0]
    if size[0] < 1e-9 or size[1] < 1e-9:
        return mesh
    scale = min(max_width / size[0], max_height / size[1], 1.0)
    mesh.apply_scale(scale)
    mesh.apply_translation(-mesh.centroid)
    return mesh


def top_surface_normal_mm() -> np.ndarray:
    dz_dx = Z_SCALE * OBJ_A / SCALE_XY
    dz_dy = Z_SCALE * OBJ_B / SCALE_XY
    normal = np.array([-dz_dx, -dz_dy, 1.0])
    return normal / np.linalg.norm(normal)


def lp_to_top_point(lp: np.ndarray) -> np.ndarray:
    z = objective(lp[0], lp[1])
    return to_mm(lp[0], lp[1], z)


def build_body_mesh() -> trimesh.Trimesh:
    """Watertight solid: base, sloped top, and vertical side walls."""
    lp_verts = FEASIBLE_VERTICES
    n = len(lp_verts)

    bottom = [to_mm(x1, x2, 0.0) for x1, x2 in lp_verts]
    top = [to_mm(x1, x2, objective(x1, x2)) for x1, x2 in lp_verts]
    vertices = np.asarray(bottom + top, dtype=float)

    faces: list[list[int]] = []

    for i, j, k in tri_fan_indices(n):
        faces.append([i, k, j])

    for i, j, k in tri_fan_indices(n):
        faces.append([n + i, n + j, n + k])

    for i in range(n):
        j = (i + 1) % n
        bi, bj = i, j
        ti, tj = n + i, n + j
        faces.append([bi, bj, tj])
        faces.append([bi, tj, ti])

    return trimesh.Trimesh(
        vertices=vertices,
        faces=np.asarray(faces, dtype=int),
        process=False,
    )


def add_quad_faces(
    faces: list[list[int]],
    i0: int,
    i1: int,
    i2: int,
    i3: int,
) -> None:
    faces.append([i0, i1, i2])
    faces.append([i0, i2, i3])


def append_vertices(
    vertices: list[np.ndarray],
    points: list[np.ndarray],
) -> list[int]:
    indices = []
    for p in points:
        vertices.append(p)
        indices.append(len(vertices) - 1)
    return indices


def segment_plane_intersection(
    p0: np.ndarray, p1: np.ndarray, k: float
) -> np.ndarray | None:
    f0 = objective(p0[0], p0[1]) - k
    f1 = objective(p1[0], p1[1]) - k
    if abs(f0) < 1e-9:
        return p0.copy()
    if abs(f1) < 1e-9:
        return p1.copy()
    if f0 * f1 > 0:
        return None
    t = f0 / (f0 - f1)
    t = min(1.0, max(0.0, t))
    return p0 + t * (p1 - p0)


def dedupe_points(points: list[np.ndarray], tol: float) -> list[np.ndarray]:
    unique: list[np.ndarray] = []
    for p in points:
        if not any(np.linalg.norm(p - q) < tol for q in unique):
            unique.append(p)
    return unique


def clip_contour_to_polygon(k: float) -> list[tuple[np.ndarray, np.ndarray]]:
    """Return chord(s) where 300*x1 + 500*x2 = k intersects the feasible polygon."""
    verts = FEASIBLE_VERTICES
    hits: list[np.ndarray] = []

    for i in range(len(verts)):
        p0 = verts[i]
        p1 = verts[(i + 1) % len(verts)]
        hit = segment_plane_intersection(p0, p1, k)
        if hit is not None:
            hits.append(hit)

    unique = dedupe_points(hits, tol=1e-6)
    if len(unique) < 2:
        return []

    best_pair: tuple[np.ndarray, np.ndarray] | None = None
    best_dist = -1.0
    for i in range(len(unique)):
        for j in range(i + 1, len(unique)):
            dist = np.linalg.norm(unique[i] - unique[j])
            if dist > best_dist:
                best_dist = dist
                best_pair = (unique[i], unique[j])

    if best_pair is None or best_dist < 1e-6:
        return []

    mid = (best_pair[0] + best_pair[1]) / 2.0
    if not point_in_polygon(mid):
        return []

    return [best_pair]


def build_contour_ridge_indices(
    p0_lp: np.ndarray,
    p1_lp: np.ndarray,
    vertices: list[np.ndarray],
    faces: list[list[int]],
) -> None:
    """Raised strip along an iso-profit line on the top surface."""
    z0 = objective(p0_lp[0], p0_lp[1])
    z1 = objective(p1_lp[0], p1_lp[1])

    base0 = to_mm(p0_lp[0], p0_lp[1], z0)
    base1 = to_mm(p1_lp[0], p1_lp[1], z1)
    up = np.array([0.0, 0.0, RIDGE_HEIGHT])
    top0 = base0 + up
    top1 = base1 + up

    seg = top1 - top0
    seg_len = np.linalg.norm(seg)
    if seg_len < 1e-6:
        return

    seg_dir = seg / seg_len
    perp = np.cross(seg_dir, [0.0, 0.0, 1.0])
    if np.linalg.norm(perp) < 1e-9:
        perp = np.array([0.0, 1.0, 0.0])
    perp = perp / np.linalg.norm(perp) * (RIDGE_WIDTH / 2.0)

    points = [
        base0 - perp,
        base0 + perp,
        base1 + perp,
        base1 - perp,
        top0 - perp,
        top0 + perp,
        top1 + perp,
        top1 - perp,
    ]
    b0l, b0r, b1r, b1l, t0l, t0r, t1r, t1l = append_vertices(vertices, points)

    add_quad_faces(faces, b0l, b1l, t1l, t0l)
    add_quad_faces(faces, b0r, t0r, t1r, b1r)
    add_quad_faces(faces, b0l, t0l, t0r, b0r)
    add_quad_faces(faces, b1l, b1r, t1r, t1l)
    add_quad_faces(faces, t0l, t1l, t1r, t0r)


def contour_label_offset_lp(p0_lp: np.ndarray, p1_lp: np.ndarray) -> np.ndarray:
    """LP-space point just below the contour chord (toward lower objective)."""
    mid = (p0_lp + p1_lp) / 2.0
    chord = p1_lp - p0_lp
    length = np.linalg.norm(chord)
    if length < 1e-9:
        return mid
    perp = np.array([-chord[1], chord[0]]) / length
    gradient = np.array([OBJ_A, OBJ_B])
    if np.dot(perp, gradient) > 0:
        perp = -perp
    return mid + perp * LABEL_OFFSET_LP


def build_contour_label_mesh(k: float, p0_lp: np.ndarray, p1_lp: np.ndarray) -> trimesh.Trimesh:
    """Etched objective equation label on the top face below a contour line."""
    label = f"{OBJECTIVE_LHS} = {k}"
    text = create_text_mesh(label)

    chord_mm = (lp_to_top_point(p1_lp) - lp_to_top_point(p0_lp))[:2]
    chord_len_mm = np.linalg.norm(chord_mm)
    x_axis_3d = lp_to_top_point(p1_lp) - lp_to_top_point(p0_lp)
    if np.linalg.norm(x_axis_3d) < 1e-9:
        return text
    x_axis_3d = x_axis_3d / np.linalg.norm(x_axis_3d)

    z_axis = top_surface_normal_mm()
    y_axis = np.cross(z_axis, x_axis_3d)
    if np.linalg.norm(y_axis) < 1e-9:
        y_axis = np.array([0.0, 1.0, 0.0])
    y_axis = y_axis / np.linalg.norm(y_axis)
    x_axis_3d = np.cross(y_axis, z_axis)
    x_axis_3d = x_axis_3d / np.linalg.norm(x_axis_3d)
    x_axis_3d, y_axis = flip_text_180(x_axis_3d, y_axis)

    text = fit_text_mesh(text, max_width=chord_len_mm * 0.9, max_height=CONTOUR_LABEL_MAX_HEIGHT_MM)

    anchor_lp = contour_label_offset_lp(p0_lp, p1_lp)
    origin = lp_to_top_point(anchor_lp) + z_axis * RIDGE_HEIGHT

    text.apply_transform(
        make_transform(origin, x_axis_3d, y_axis, z_axis)
    )
    return text


def build_wall_label_mesh(
    p0_lp: np.ndarray,
    p1_lp: np.ndarray,
    label: str,
) -> trimesh.Trimesh:
    """Etched constraint label on the exterior of a vertical side wall."""
    z0 = objective(p0_lp[0], p0_lp[1])
    z1 = objective(p1_lp[0], p1_lp[1])

    bl = to_mm(p0_lp[0], p0_lp[1], 0.0)
    br = to_mm(p1_lp[0], p1_lp[1], 0.0)
    tl = to_mm(p0_lp[0], p0_lp[1], z0)
    tr = to_mm(p1_lp[0], p1_lp[1], z1)

    x_axis = br - bl
    wall_width = np.linalg.norm(x_axis)
    if wall_width < 1e-6:
        raise ValueError("Degenerate wall edge.")
    x_axis = x_axis / wall_width

    z_axis = np.array([outward_normal_2d(p0_lp, p1_lp)[0], outward_normal_2d(p0_lp, p1_lp)[1], 0.0])
    y_axis = np.array([0.0, 0.0, 1.0])

    wall_height = max(np.linalg.norm(tl - bl), np.linalg.norm(tr - br))
    text = create_text_mesh(label)
    text = fit_text_mesh(text, max_width=wall_width * 0.85, max_height=wall_height * 0.22)

    bottom_mid = 0.5 * (bl + br)
    top_mid = 0.5 * (tl + tr)
    origin = bottom_mid + WALL_LABEL_V_FRACTION * (top_mid - bottom_mid) + z_axis * TEXT_DEPTH
    text.apply_transform(make_transform(origin, x_axis, y_axis, z_axis))
    return text


def mesh_to_indexed_parts(
    mesh: trimesh.Trimesh,
    vertices: list[np.ndarray],
    faces: list[list[int]],
) -> None:
    base = len(vertices)
    for vertex in mesh.vertices:
        vertices.append(vertex)
    for face in mesh.faces:
        faces.append([base + i for i in face])


def build_accent_mesh() -> trimesh.Trimesh:
    """Top contour ridges, objective labels, and etched wall constraint labels."""
    vertices: list[np.ndarray] = []
    faces: list[list[int]] = []

    for level in CONTOUR_LEVELS:
        for p0, p1 in clip_contour_to_polygon(level):
            build_contour_ridge_indices(p0, p1, vertices, faces)
            label_mesh = build_contour_label_mesh(level, p0, p1)
            mesh_to_indexed_parts(label_mesh, vertices, faces)

    n = len(FEASIBLE_VERTICES)
    for i in range(n):
        p0 = FEASIBLE_VERTICES[i]
        p1 = FEASIBLE_VERTICES[(i + 1) % n]
        label_mesh = build_wall_label_mesh(p0, p1, EDGE_CONSTRAINT_LABELS[i])
        mesh_to_indexed_parts(label_mesh, vertices, faces)

    if not vertices:
        raise RuntimeError("Accent mesh has no geometry.")

    return trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=float),
        faces=np.asarray(faces, dtype=int),
        process=False,
    )


def validate_mesh(mesh: trimesh.Trimesh, name: str, require_watertight: bool) -> None:
    print(f"{name}:")
    print(f"  vertices: {len(mesh.vertices)}, faces: {len(mesh.faces)}")
    print(f"  watertight: {mesh.is_watertight}, winding consistent: {mesh.is_winding_consistent}")
    if require_watertight and not mesh.is_watertight:
        raise RuntimeError(f"{name} is not watertight.")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    body = build_body_mesh()
    accents = build_accent_mesh()

    body_path = OUTPUT_DIR / "wyndor_body.stl"
    accents_path = OUTPUT_DIR / "wyndor_accents.stl"

    body.export(body_path)
    accents.export(accents_path)

    validate_mesh(body, "wyndor_body.stl", require_watertight=True)
    validate_mesh(accents, "wyndor_accents.stl", require_watertight=False)

    bounds = body.bounds
    size = bounds[1] - bounds[0]
    print(f"\nBody dimensions (mm): X={size[0]:.1f}, Y={size[1]:.1f}, Z={size[2]:.1f}")
    print(f"Contour levels included: {CONTOUR_LEVELS}")
    print(f"\nExported:\n  {body_path}\n  {accents_path}")


if __name__ == "__main__":
    main()
