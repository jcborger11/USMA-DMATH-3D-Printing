#!/usr/bin/env python3
"""Generate STL meshes for the Wyndor Glass Co. LP 3D visualization."""

from __future__ import annotations

import argparse
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

# Inset accent geometry (millimeters).
RIDGE_WIDTH = 1.0
GROOVE_DEPTH = 0.5
TEXT_FONT_SIZE = 6.0
LABEL_INSET_DEPTH = 0.5
INSET_CLEARANCE = 0.05
CONTOUR_LABEL_GAP_MM = 1.5  # min clearance from groove edge to nearest equation glyph
WALL_LABEL_V_FRACTION = 0.18  # default vertical position: fraction up from base
WALL_LABEL_HEIGHT_FRAC = 0.22  # default max text height as fraction of local wall height
CONTOUR_LABEL_FONT_SIZE = 8.0
CONTOUR_LABEL_INSET_DEPTH = 0.8
CONTOUR_LABEL_MAX_HEIGHT_MM = 3.7

# Per-contour label placement (defaults: chord_fraction=0.5 along p0→p1).
CONTOUR_LABEL_OVERRIDES: dict[float, dict[str, float]] = {
    1200: {"chord_fraction": 0.54},  # balance: keep 300 and = 1200 on top face
}

# Per-edge wall label placement (defaults: h_fraction=0.5, v_fraction=WALL_LABEL_V_FRACTION).
MATCH_DIAGONAL_HEIGHT_LABELS = {"x₁ ≤ 4", "x₂ ≤ 6", "x₁ ≥ 0"}
WALL_LABEL_OVERRIDES: dict[str, dict[str, float]] = {
    "x₁ ≥ 0": {"v_fraction": 0.26, "h_fraction": 0.5},
    "x₂ ≥ 0": {
        "h_fraction": 0.72,
        "v_fraction": 0.40,
        "max_height_mm": 5.5,
    },
}

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
BOOLEAN_ENGINE = "manifold"

# Single-filament print: engraved cavities in body only, no accent STL.
BODY_ONLY = True


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


def wall_label_settings(label: str) -> dict[str, float]:
    overrides = WALL_LABEL_OVERRIDES.get(label, {})
    max_height_mm = overrides.get("max_height_mm", -1.0)
    if max_height_mm < 0 and label in MATCH_DIAGONAL_HEIGHT_LABELS:
        max_height_mm = reference_wall_label_max_height_mm()
    return {
        "h_fraction": overrides.get("h_fraction", 0.5),
        "v_fraction": overrides.get("v_fraction", WALL_LABEL_V_FRACTION),
        "max_height_mm": max_height_mm,
    }


def create_text_volume(
    text: str,
    depth: float,
    xy_buffer: float = 0.0,
    font_size: float = TEXT_FONT_SIZE,
) -> trimesh.Trimesh:
    """Extrude text from local z=0 into +Z by depth (anchored on the opening face)."""
    path = TextPath(
        (0, 0),
        text,
        prop=FontProperties(family="DejaVu Sans", size=font_size),
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
        if xy_buffer > 0.0:
            polygon = polygon.buffer(xy_buffer)
            if polygon.is_empty:
                continue
            if polygon.geom_type == "MultiPolygon":
                polygon = max(polygon.geoms, key=lambda g: g.area)
        parts.append(trimesh.creation.extrude_polygon(polygon, height=depth))
    if not parts:
        raise ValueError(f"Could not generate text geometry for: {text!r}")
    mesh = trimesh.util.concatenate(parts)
    center_xy = 0.5 * (mesh.bounds[0, :2] + mesh.bounds[1, :2])
    mesh.apply_translation([-center_xy[0], -center_xy[1], -mesh.bounds[0, 2]])
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
    center_xy = 0.5 * (mesh.bounds[0, :2] + mesh.bounds[1, :2])
    mesh.apply_translation([-center_xy[0], -center_xy[1], -mesh.bounds[0, 2]])
    return mesh


def top_surface_normal_mm() -> np.ndarray:
    dz_dx = Z_SCALE * OBJ_A / SCALE_XY
    dz_dy = Z_SCALE * OBJ_B / SCALE_XY
    normal = np.array([-dz_dx, -dz_dy, 1.0])
    return normal / np.linalg.norm(normal)


def lp_to_top_point(lp: np.ndarray) -> np.ndarray:
    z = objective(lp[0], lp[1])
    return to_mm(lp[0], lp[1], z)


def apply_transform(mesh: trimesh.Trimesh, matrix: np.ndarray) -> trimesh.Trimesh:
    result = mesh.copy()
    result.apply_transform(matrix)
    return result


def prepare_for_boolean(mesh: trimesh.Trimesh, merge: bool = True) -> trimesh.Trimesh:
    result = mesh.copy()
    if merge:
        result.merge_vertices()
    result.fix_normals()
    return result


def boolean_union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    prepared = [prepare_for_boolean(mesh) for mesh in meshes]
    if len(prepared) == 1:
        return prepared[0]
    return trimesh.boolean.union(prepared, engine=BOOLEAN_ENGINE)


def boolean_difference(base: trimesh.Trimesh, cutters: trimesh.Trimesh) -> trimesh.Trimesh:
    return trimesh.boolean.difference(
        [prepare_for_boolean(base, merge=False), prepare_for_boolean(cutters)],
        engine=BOOLEAN_ENGINE,
        check_volume=False,
    )


def build_base_polyhedron() -> trimesh.Trimesh:
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


def contour_label_settings(k: float) -> dict[str, float]:
    overrides = CONTOUR_LABEL_OVERRIDES.get(k, {})
    return {
        "chord_fraction": overrides.get("chord_fraction", 0.5),
    }


def contour_label_offset_lp(
    k: float,
    p0_lp: np.ndarray,
    p1_lp: np.ndarray,
) -> np.ndarray:
    """LP-space point below the contour chord (toward lower objective), clearing groove + text."""
    settings = contour_label_settings(k)
    offset_lp = (
        RIDGE_WIDTH / 2.0 + CONTOUR_LABEL_GAP_MM + CONTOUR_LABEL_MAX_HEIGHT_MM / 2.0
    ) / SCALE_XY
    base_lp = p0_lp + settings["chord_fraction"] * (p1_lp - p0_lp)
    chord = p1_lp - p0_lp
    length = np.linalg.norm(chord)
    if length < 1e-9:
        return base_lp
    perp = np.array([-chord[1], chord[0]]) / length
    gradient = np.array([OBJ_A, OBJ_B])
    if np.dot(perp, gradient) > 0:
        perp = -perp
    return base_lp + perp * offset_lp


def reference_wall_label_max_height_mm() -> float:
    """Max text height for the diagonal constraint label (reference for other walls)."""
    p0, p1 = FEASIBLE_VERTICES[2], FEASIBLE_VERTICES[3]
    _, max_h = wall_label_max_size(p0, p1, "3x₁ + 2x₂ ≤ 18")
    return max_h


def wall_label_transform(
    p0_lp: np.ndarray,
    p1_lp: np.ndarray,
    label: str,
) -> np.ndarray:
    """4x4 transform: local +Z points into the body from the exterior wall face."""
    settings = wall_label_settings(label)
    h_fraction = settings["h_fraction"]
    v_fraction = settings["v_fraction"]

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

    outward = np.array(
        [outward_normal_2d(p0_lp, p1_lp)[0], outward_normal_2d(p0_lp, p1_lp)[1], 0.0]
    )
    y_axis = np.array([0.0, 0.0, 1.0])
    z_axis = -outward

    anchor_bottom = bl + h_fraction * (br - bl)
    anchor_top = tl + h_fraction * (tr - tl)
    origin = anchor_bottom + v_fraction * (anchor_top - anchor_bottom)
    return make_transform(origin, x_axis, y_axis, z_axis)


def wall_label_max_size(
    p0_lp: np.ndarray,
    p1_lp: np.ndarray,
    label: str,
) -> tuple[float, float]:
    settings = wall_label_settings(label)
    h_fraction = settings["h_fraction"]

    z0 = objective(p0_lp[0], p0_lp[1])
    z1 = objective(p1_lp[0], p1_lp[1])
    bl = to_mm(p0_lp[0], p0_lp[1], 0.0)
    br = to_mm(p1_lp[0], p1_lp[1], 0.0)
    tl = to_mm(p0_lp[0], p0_lp[1], z0)
    tr = to_mm(p1_lp[0], p1_lp[1], z1)

    anchor_bottom = bl + h_fraction * (br - bl)
    anchor_top = tl + h_fraction * (tr - tl)
    local_height = np.linalg.norm(anchor_top - anchor_bottom)
    wall_width = np.linalg.norm(br - bl)

    if settings["max_height_mm"] > 0:
        max_h = settings["max_height_mm"]
    else:
        max_h = local_height * WALL_LABEL_HEIGHT_FRAC
    return wall_width * 0.85, max_h


def build_wall_label_pair(
    p0_lp: np.ndarray,
    p1_lp: np.ndarray,
    label: str,
) -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    transform = wall_label_transform(p0_lp, p1_lp, label)
    max_w, max_h = wall_label_max_size(p0_lp, p1_lp, label)

    cavity_local = fit_text_mesh(
        create_text_volume(
            label,
            LABEL_INSET_DEPTH + INSET_CLEARANCE,
            xy_buffer=INSET_CLEARANCE / 2.0,
        ),
        max_w,
        max_h,
    )
    cavity = apply_transform(cavity_local, transform)
    if BODY_ONLY:
        return cavity, trimesh.Trimesh()
    fill_local = fit_text_mesh(create_text_volume(label, LABEL_INSET_DEPTH), max_w, max_h)
    return cavity, apply_transform(fill_local, transform)


def contour_label_transform(
    k: float,
    p0_lp: np.ndarray,
    p1_lp: np.ndarray,
) -> np.ndarray | None:
    """4x4 transform: local +Z points into the body from the top surface."""
    x_axis_3d = lp_to_top_point(p1_lp) - lp_to_top_point(p0_lp)
    if np.linalg.norm(x_axis_3d) < 1e-9:
        return None

    x_axis_3d = x_axis_3d / np.linalg.norm(x_axis_3d)
    outward = top_surface_normal_mm()
    y_axis = np.cross(outward, x_axis_3d)
    if np.linalg.norm(y_axis) < 1e-9:
        y_axis = np.array([0.0, 1.0, 0.0])
    y_axis = y_axis / np.linalg.norm(y_axis)
    x_axis_3d = np.cross(y_axis, outward)
    x_axis_3d = x_axis_3d / np.linalg.norm(x_axis_3d)
    x_axis_3d, y_axis = flip_text_180(x_axis_3d, y_axis)

    anchor_lp = contour_label_offset_lp(k, p0_lp, p1_lp)
    origin = lp_to_top_point(anchor_lp)
    return make_transform(origin, x_axis_3d, y_axis, -outward)


def contour_label_max_size(p0_lp: np.ndarray, p1_lp: np.ndarray) -> tuple[float, float]:
    chord_mm = (lp_to_top_point(p1_lp) - lp_to_top_point(p0_lp))[:2]
    chord_len_mm = np.linalg.norm(chord_mm)
    return chord_len_mm * 0.9, CONTOUR_LABEL_MAX_HEIGHT_MM


def build_contour_label_pair(
    k: float,
    p0_lp: np.ndarray,
    p1_lp: np.ndarray,
) -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    label = f"{OBJECTIVE_LHS} = {k}"
    transform = contour_label_transform(k, p0_lp, p1_lp)
    if transform is None:
        empty = trimesh.Trimesh()
        return empty, empty

    max_w, max_h = contour_label_max_size(p0_lp, p1_lp)
    cavity_local = fit_text_mesh(
        create_text_volume(
            label,
            CONTOUR_LABEL_INSET_DEPTH + INSET_CLEARANCE,
            xy_buffer=INSET_CLEARANCE / 2.0,
            font_size=CONTOUR_LABEL_FONT_SIZE,
        ),
        max_w,
        max_h,
    )
    cavity = apply_transform(cavity_local, transform)
    if BODY_ONLY:
        return cavity, trimesh.Trimesh()
    fill_local = fit_text_mesh(
        create_text_volume(
            label,
            CONTOUR_LABEL_INSET_DEPTH,
            font_size=CONTOUR_LABEL_FONT_SIZE,
        ),
        max_w,
        max_h,
    )
    return cavity, apply_transform(fill_local, transform)


def build_contour_groove_mesh(p0_lp: np.ndarray, p1_lp: np.ndarray, depth: float) -> trimesh.Trimesh:
    """Vertical groove strip on the top surface, extruded downward into the body."""
    z0 = objective(p0_lp[0], p0_lp[1])
    z1 = objective(p1_lp[0], p1_lp[1])

    top0 = to_mm(p0_lp[0], p0_lp[1], z0)
    top1 = to_mm(p1_lp[0], p1_lp[1], z1)
    down = np.array([0.0, 0.0, -depth])
    bottom0 = top0 + down
    bottom1 = top1 + down

    seg = top1 - top0
    seg_len = np.linalg.norm(seg)
    if seg_len < 1e-6:
        return trimesh.Trimesh()

    seg_dir = seg / seg_len
    perp = np.cross(seg_dir, [0.0, 0.0, 1.0])
    if np.linalg.norm(perp) < 1e-9:
        perp = np.array([0.0, 1.0, 0.0])
    perp = perp / np.linalg.norm(perp) * (RIDGE_WIDTH / 2.0)

    vertices = np.array(
        [
            top0 - perp,
            top0 + perp,
            top1 + perp,
            top1 - perp,
            bottom0 - perp,
            bottom0 + perp,
            bottom1 + perp,
            bottom1 - perp,
        ],
        dtype=float,
    )
    faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [4, 6, 5],
            [4, 7, 6],
            [0, 4, 5],
            [0, 5, 1],
            [1, 5, 6],
            [1, 6, 2],
            [2, 6, 7],
            [2, 7, 3],
            [3, 7, 4],
            [3, 4, 0],
        ],
        dtype=int,
    )
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def build_contour_groove_pair(
    p0_lp: np.ndarray,
    p1_lp: np.ndarray,
) -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    cavity = build_contour_groove_mesh(p0_lp, p1_lp, GROOVE_DEPTH + INSET_CLEARANCE)
    if BODY_ONLY:
        return cavity, trimesh.Trimesh()
    fill = build_contour_groove_mesh(p0_lp, p1_lp, GROOVE_DEPTH)
    return cavity, fill


def collect_inset_parts() -> tuple[list[trimesh.Trimesh], list[trimesh.Trimesh]]:
    cavities: list[trimesh.Trimesh] = []
    fills: list[trimesh.Trimesh] = []

    for level in CONTOUR_LEVELS:
        for p0, p1 in clip_contour_to_polygon(level):
            cavity, fill = build_contour_groove_pair(p0, p1)
            if len(cavity.vertices) > 0:
                cavities.append(cavity)
                if not BODY_ONLY and len(fill.vertices) > 0:
                    fills.append(fill)
            cavity, fill = build_contour_label_pair(level, p0, p1)
            if len(cavity.vertices) > 0:
                cavities.append(cavity)
                if not BODY_ONLY and len(fill.vertices) > 0:
                    fills.append(fill)

    n = len(FEASIBLE_VERTICES)
    for i in range(n):
        p0 = FEASIBLE_VERTICES[i]
        p1 = FEASIBLE_VERTICES[(i + 1) % n]
        cavity, fill = build_wall_label_pair(p0, p1, EDGE_CONSTRAINT_LABELS[i])
        cavities.append(cavity)
        if not BODY_ONLY and len(fill.vertices) > 0:
            fills.append(fill)

    if not cavities:
        raise RuntimeError("No inset accent geometry generated.")
    return cavities, fills


def build_body_mesh(cavities: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    """Watertight body with grooves and label cavities cut in for accent inlays."""
    base = build_base_polyhedron()
    cutters = boolean_union(cavities)
    return boolean_difference(base, cutters)


def build_accent_mesh(fills: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    """Inlay fills for contour grooves, objective labels, and wall constraint labels."""
    return trimesh.util.concatenate(fills)


def validate_mesh(mesh: trimesh.Trimesh, name: str, require_watertight: bool) -> None:
    print(f"{name}:")
    print(f"  vertices: {len(mesh.vertices)}, faces: {len(mesh.faces)}")
    print(f"  watertight: {mesh.is_watertight}, winding consistent: {mesh.is_winding_consistent}")
    if require_watertight and not mesh.is_watertight:
        raise RuntimeError(f"{name} is not watertight.")


def launch_rotatable_preview(body: trimesh.Trimesh) -> None:
    """Open pyglet window to inspect the generated body mesh."""
    from preview import show_interactive

    print("\nOpening rotatable preview (drag to rotate, scroll to zoom)...")
    show_interactive(body, None)


def main(show_preview: bool = True) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cavities, fills = collect_inset_parts()
    body = build_body_mesh(cavities)

    body_path = OUTPUT_DIR / "wyndor_body.stl"
    body.export(body_path)
    validate_mesh(body, "wyndor_body.stl", require_watertight=True)

    exported = [body_path]
    if BODY_ONLY:
        print("\nBody-only mode: skipping wyndor_accents.stl")
    else:
        accents = build_accent_mesh(fills)
        accents_path = OUTPUT_DIR / "wyndor_accents.stl"
        accents.export(accents_path)
        validate_mesh(accents, "wyndor_accents.stl", require_watertight=False)
        exported.append(accents_path)

    bounds = body.bounds
    size = bounds[1] - bounds[0]
    print(f"\nBody dimensions (mm): X={size[0]:.1f}, Y={size[1]:.1f}, Z={size[2]:.1f}")
    print(f"Contour levels included: {CONTOUR_LEVELS}")
    print(f"Inset depths: grooves={GROOVE_DEPTH} mm, wall labels={LABEL_INSET_DEPTH} mm, contour labels={CONTOUR_LABEL_INSET_DEPTH} mm")
    print("\nExported:")
    for path in exported:
        print(f"  {path}")

    if show_preview:
        launch_rotatable_preview(body)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Wyndor LP STL files.")
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Skip opening the rotatable pyglet preview after export.",
    )
    args = parser.parse_args()
    main(show_preview=not args.no_preview)
