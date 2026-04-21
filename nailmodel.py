from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, NamedTuple, TypedDict, Self
import math

import numpy as np
import numpy.typing as npt
import open3d as o3d
from scipy.interpolate import griddata
from scipy.spatial.transform import Rotation as R
from shapely.geometry import Point, Polygon

ArrayLike = npt.ArrayLike
FloatArray = npt.NDArray[np.float64]
Vec3 = FloatArray
Points3D = FloatArray

InputPointName = Literal[
    "A", "B", "C", "D", "E", "F",
    "A_P_AF", "D_P_CD", "B_P_AB", "F_P_AF",
    "AB_P2", "AB_P3", "BC_P2", "CD_P1",
    "AF_P2", "AF_P3", "FE_P2", "ED_P1",
    "A_P1_G", "G", "A_P1_H", "H", "D_P1_I", "I", "D_P1_J", "J",
]
DerivedPointName = Literal[
    "AB_P1", "AB_P4", "BC_P1", "CD_P2", "AF_P1", "AF_P4", "FE_P1", "ED_P2"
]
PointName = InputPointName | DerivedPointName
CurveName = Literal["AB", "BC", "CD", "AF", "FE", "ED", "AGH", "JDI"]

ALL_INPUT_POINT_NAMES: Final[tuple[InputPointName, ...]] = (
    "A", "B", "C", "D", "E", "F",
    "A_P_AF", "D_P_CD", "B_P_AB", "F_P_AF",
    "AB_P2", "AB_P3", "BC_P2", "CD_P1",
    "AF_P2", "AF_P3", "FE_P2", "ED_P1",
    "A_P1_G", "G", "A_P1_H", "H", "D_P1_I", "I", "D_P1_J", "J",
)

ZERO_Z_COMPAT_POINT_NAMES: Final[tuple[InputPointName, ...]] = (
    "A", "B", "C", "D", "E", "F",
    "A_P_AF", "D_P_CD", "B_P_AB", "F_P_AF",
    "AB_P2", "AB_P3", "BC_P2", "CD_P1",
    "AF_P2", "AF_P3", "FE_P2", "ED_P1",
)

ROOT_SIDE_POINT_NAMES: Final[tuple[InputPointName, ...]] = ("A_P1_G", "G", "A_P1_H", "H")
TIP_SIDE_POINT_NAMES: Final[tuple[InputPointName, ...]] = ("D_P1_I", "I", "D_P1_J", "J")

ALL_DERIVED_POINT_NAMES: Final[tuple[DerivedPointName, ...]] = (
    "AB_P1", "AB_P4", "BC_P1", "CD_P2", "AF_P1", "AF_P4", "FE_P1", "ED_P2"
)

CURVE_DEFINITIONS: Final[dict[CurveName, tuple[PointName, ...]]] = {
    "AB": ("A", "AB_P1", "AB_P2", "AB_P3", "AB_P4", "B"),
    "BC": ("B", "BC_P1", "BC_P2", "C"),
    "CD": ("C", "CD_P1", "CD_P2", "D"),
    "AF": ("A", "AF_P1", "AF_P2", "AF_P3", "AF_P4", "F"),
    "FE": ("F", "FE_P1", "FE_P2", "E"),
    "ED": ("E", "ED_P1", "ED_P2", "D"),
    "AGH": ("G", "A_P1_G", "A", "A_P1_H", "H"),
    "JDI": ("J", "D_P1_J", "D", "D_P1_I", "I"),
}


class NailModelInit(TypedDict, total=False):
    AD_arc: float
    A_tangent: float
    xy_rotation: float
    A: ArrayLike
    B: ArrayLike
    C: ArrayLike
    D: ArrayLike
    E: ArrayLike
    F: ArrayLike
    A_P_AF: ArrayLike
    D_P_CD: ArrayLike
    B_P_AB: ArrayLike
    F_P_AF: ArrayLike
    AB_P2: ArrayLike
    AB_P3: ArrayLike
    BC_P2: ArrayLike
    CD_P1: ArrayLike
    AF_P2: ArrayLike
    AF_P3: ArrayLike
    FE_P2: ArrayLike
    ED_P1: ArrayLike
    A_P1_G: ArrayLike
    G: ArrayLike
    A_P1_H: ArrayLike
    H: ArrayLike
    D_P1_I: ArrayLike
    I: ArrayLike  # noqa: E741
    D_P1_J: ArrayLike
    J: ArrayLike


@dataclass(slots=True, kw_only=True)
class ModelParams:
    AD_arc: float = math.pi / 6
    # Angle between +Z axis and AD' at A in XZ plane.
    A_tangent: float = math.radians(86.0)
    xy_rotation: float = 0.0


@dataclass(slots=True)
class ArcGeometry:
    points: Points3D
    center: Vec3
    radius: float
    normal: Vec3
    end_point: Vec3


@dataclass(slots=True)
class BuildArtifacts:
    curve_points: dict[CurveName, Points3D]
    abcdef_edge_points: Points3D
    edge_points: Points3D
    bone_points: Points3D
    all_curve_points: Points3D
    filling_surface_points: Points3D
    clipped_filling_surface_points: Points3D
    all_filling_surface_points: Points3D
    mesh_points: Points3D
    arc_geometry: ArcGeometry
    mesh: o3d.geometry.TriangleMesh | None = None


class Circle3D(NamedTuple):
    center: Vec3
    radius: float


def _as_vec3(value: ArrayLike, *, name: str) -> Vec3:
    arr = np.asarray(value, dtype=np.float64)
    if arr.shape != (3,):
        raise ValueError(f"{name} must have shape (3,), got {arr.shape}")
    return arr


def _as_compact_point(value: ArrayLike, *, name: str) -> npt.NDArray[np.float64]:
    arr = np.asarray(value, dtype=np.float64)
    if arr.ndim != 1 or arr.shape[0] not in (2, 3):
        raise ValueError(f"{name} must have shape (2,) or (3,), got {arr.shape}")
    return arr


def _expand_input_point(
    name: InputPointName,
    value: ArrayLike,
    *,
    a_x: float,
    d_x: float,
) -> Vec3:
    arr = _as_compact_point(value, name=name)
    if arr.shape[0] == 3:
        return _as_vec3(arr, name=name)

    if name in ZERO_Z_COMPAT_POINT_NAMES:
        return np.array([arr[0], arr[1], 0.0], dtype=np.float64)

    if name in ROOT_SIDE_POINT_NAMES:
        return np.array([a_x, arr[0], arr[1]], dtype=np.float64)

    if name in TIP_SIDE_POINT_NAMES:
        return np.array([d_x, arr[0], arr[1]], dtype=np.float64)

    raise ValueError(f"Unsupported input point name: {name}")


def _expand_initial_points(provided: NailModelInit) -> dict[InputPointName, Vec3]:
    a = _expand_input_point("A", provided.get("A", (0.0, 0.0, 0.0)), a_x=0.0, d_x=0.0)
    d = _expand_input_point("D", provided.get("D", (0.0, 0.0, 0.0)), a_x=float(a[0]), d_x=0.0)

    a_x = float(a[0])
    d_x = float(d[0])

    expanded: dict[InputPointName, Vec3] = {}
    for name in ALL_INPUT_POINT_NAMES:
        expanded[name] = _expand_input_point(
            name,
            provided.get(name, (0.0, 0.0, 0.0)),
            a_x=a_x,
            d_x=d_x,
        )
    return expanded


def _as_points3d(value: ArrayLike, *, name: str) -> Points3D:
    arr = np.asarray(value, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError(f"{name} must have shape (N, 3), got {arr.shape}")
    return arr


class Bezier:
    def __init__(self, control_points: ArrayLike) -> None:
        self.control_points: Points3D = _as_points3d(control_points, name="control_points")
        self.degree: int = self.control_points.shape[0] - 1

    def evaluate(self, t: float) -> Vec3:
        point = np.zeros(self.control_points.shape[1], dtype=np.float64)
        for j in range(self.degree + 1):
            coef = math.comb(self.degree, j) * (t ** j) * ((1 - t) ** (self.degree - j))
            point += coef * self.control_points[j]
        return point

    def get_points(self, num_points: int = 100) -> Points3D:
        t_values = np.linspace(0.0, 1.0, num_points)
        points = [self.evaluate(float(t)) for t in t_values]
        return _as_points3d(points, name="bezier_points")


class NailModel:
    def __init__(self, initial_geometry: NailModelInit | None = None) -> None:
        provided = initial_geometry or {}
        ad_arc_value = float(provided.get("AD_arc", math.pi / 6))
        a_tangent_default = math.radians(86.0)

        self.params = ModelParams(
            AD_arc=ad_arc_value,
            A_tangent=float(provided.get("A_tangent", a_tangent_default)),
            xy_rotation=float(provided.get("xy_rotation", 0.0)),
        )

        expanded_points = _expand_initial_points(provided)
        self._original_input_points: dict[InputPointName, Vec3] = {
            name: expanded_points[name].copy() for name in ALL_INPUT_POINT_NAMES
        }
        self._points: dict[PointName, Vec3] = {name: expanded_points[name] for name in ALL_INPUT_POINT_NAMES}
        for name in ALL_DERIVED_POINT_NAMES:
            self._points[name] = np.zeros(3, dtype=np.float64)

        self._bezier_curves: dict[CurveName, Bezier] = {}
        self.artifacts: BuildArtifacts | None = None
        self._rebuild_geometry()

    def _rebuild_geometry(self) -> None:
        self._normalize_points_for_construction()
        self._update_derived_points()
        self._update_all_curves()
        self.artifacts = None

    def _normalize_points_for_construction(self) -> None:
        a_origin = self._points["A"].copy()
        for name in ALL_INPUT_POINT_NAMES:
            self._points[name] = self._points[name] - a_origin

        ad_vec = self._points["D"] - self._points["A"]
        ad_xy_norm = np.linalg.norm(ad_vec[:2])
        if ad_xy_norm < 1e-8:
            raise ValueError("Points A and D are too close in XY; cannot align AD to +X.")

        theta = math.atan2(float(ad_vec[1]), float(ad_vec[0]))
        rot_z = R.from_euler("z", -theta).as_matrix()
        for name in ALL_INPUT_POINT_NAMES:
            self._points[name] = rot_z @ self._points[name]

        for name in ("A", "B", "C", "D", "E", "F"):
            self._points[name][2] = 0.0

    def _update_derived_points(self) -> None:
        self._points["AB_P1"] = self._points["A"] + (self._points["A"] - self._points["A_P_AF"])
        self._points["AB_P4"] = self._points["B_P_AB"]
        self._points["BC_P1"] = self._points["B"] + (self._points["B"] - self._points["B_P_AB"])
        self._points["CD_P2"] = self._points["D_P_CD"]
        self._points["AF_P1"] = self._points["A_P_AF"]
        self._points["AF_P4"] = self._points["F_P_AF"]
        self._points["FE_P1"] = self._points["F"] + (self._points["F"] - self._points["F_P_AF"])
        self._points["ED_P2"] = self._points["D"] + (self._points["D"] - self._points["D_P_CD"])

    def _get_control_points_for_curve(self, curve_name: CurveName) -> list[Vec3]:
        point_names = CURVE_DEFINITIONS[curve_name]
        return [self._points[name] for name in point_names]

    def _update_all_curves(self) -> None:
        for name in CURVE_DEFINITIONS:
            control_points_data = self._get_control_points_for_curve(name)
            self._bezier_curves[name] = Bezier(control_points_data)

    def set_point(self, name: InputPointName, coordinates: ArrayLike) -> None:
        self._original_input_points[name] = _expand_input_point(
            name,
            coordinates,
            a_x=float(self._original_input_points["A"][0]),
            d_x=float(self._original_input_points["D"][0]),
        )
        if name == "A":
            a_x = float(self._original_input_points["A"][0])
            for related_name in ROOT_SIDE_POINT_NAMES:
                yz = self._original_input_points[related_name][1:3]
                self._original_input_points[related_name] = np.array([a_x, yz[0], yz[1]], dtype=np.float64)
        if name == "D":
            d_x = float(self._original_input_points["D"][0])
            for related_name in TIP_SIDE_POINT_NAMES:
                yz = self._original_input_points[related_name][1:3]
                self._original_input_points[related_name] = np.array([d_x, yz[0], yz[1]], dtype=np.float64)

        self._points[name] = _expand_input_point(
            name,
            coordinates,
            a_x=float(self._points["A"][0]),
            d_x=float(self._points["D"][0]),
        )
        self._rebuild_geometry()

    def get_point(self, name: PointName) -> Vec3:
        return self._points[name]

    def get_curve(self, curve_name: CurveName) -> Bezier:
        return self._bezier_curves[curve_name]

    def get_all_curve_points(self) -> dict[CurveName, Points3D]:
        return {name: curve.get_points() for name, curve in self._bezier_curves.items()}

    def _to_artifact_frame(self, point: Vec3) -> Vec3:
        a_origin = self._original_input_points["A"]
        d_point = self._original_input_points["D"]

        ad_vec = d_point - a_origin
        ad_xy_norm = np.linalg.norm(ad_vec[:2])
        if ad_xy_norm < 1e-8:
            raise ValueError("Points A and D are too close in XY; cannot map point into artifact frame.")

        theta_align = math.atan2(float(ad_vec[1]), float(ad_vec[0]))
        theta = -(theta_align + float(self.params.xy_rotation))
        rot_z = R.from_euler("z", theta).as_matrix()

        shifted = np.asarray(point, dtype=np.float64) - a_origin
        mapped = rot_z @ shifted
        return _as_vec3(mapped, name="artifact_frame_point")

    def _sample_surface_z_from_xy(self, query_xy: npt.NDArray[np.float64], surface_points: Points3D) -> npt.NDArray[np.float64]:
        if query_xy.ndim != 2 or query_xy.shape[1] != 2:
            raise ValueError(f"query_xy must have shape (N, 2), got {query_xy.shape}")

        if surface_points.shape[0] == 0:
            raise ValueError("Cannot recover input point z from empty surface points.")

        sampled_z = griddata(surface_points[:, :2], surface_points[:, 2], query_xy, method="linear")
        sampled_z = np.asarray(sampled_z, dtype=np.float64)

        missing_mask = np.isnan(sampled_z)
        if np.any(missing_mask):
            nearest_z = griddata(surface_points[:, :2], surface_points[:, 2], query_xy[missing_mask], method="nearest")
            sampled_z[missing_mask] = np.asarray(nearest_z, dtype=np.float64)

        return sampled_z

    def get_input_points(self) -> dict[InputPointName, list[float]]:
        """Return input points with Z recovered from vertical intersection on built surface.

        This method must be called after build(). Returned XY keeps the original
        user input coordinate system. Z is recovered by vertical projection onto
        the built filling surface. Root/tip side points are excluded.
        """
        artifacts = self._require_artifacts()
        names = list(ZERO_Z_COMPAT_POINT_NAMES)
        query_points_in_artifact_frame = [self._to_artifact_frame(self._original_input_points[name]) for name in names]
        query_xy = np.asarray([[p[0], p[1]] for p in query_points_in_artifact_frame], dtype=np.float64)
        sampled_z = self._sample_surface_z_from_xy(query_xy, artifacts.filling_surface_points)

        z_offset = float(self._original_input_points["A"][2])
        recovered_points: dict[InputPointName, list[float]] = {}
        for idx, name in enumerate(names):
            p = self._original_input_points[name].copy()
            p[2] = float(sampled_z[idx]) + z_offset
            recovered_points[name] = [float(p[0]), float(p[1]), float(p[2])]

        return recovered_points

    @property
    def A(self) -> Vec3:
        return self._points["A"]

    @A.setter
    def A(self, value: ArrayLike) -> None:
        self.set_point("A", value)

    @property
    def B(self) -> Vec3:
        return self._points["B"]

    @B.setter
    def B(self, value: ArrayLike) -> None:
        self.set_point("B", value)

    @property
    def C(self) -> Vec3:
        return self._points["C"]

    @C.setter
    def C(self, value: ArrayLike) -> None:
        self.set_point("C", value)

    @property
    def D(self) -> Vec3:
        return self._points["D"]

    @D.setter
    def D(self, value: ArrayLike) -> None:
        self.set_point("D", value)

    @property
    def E(self) -> Vec3:
        return self._points["E"]

    @E.setter
    def E(self, value: ArrayLike) -> None:
        self.set_point("E", value)

    @property
    def F(self) -> Vec3:
        return self._points["F"]

    @F.setter
    def F(self, value: ArrayLike) -> None:
        self.set_point("F", value)

    @property
    def G(self) -> Vec3:
        return self._points["G"]

    @property
    def H(self) -> Vec3:
        return self._points["H"]

    @property
    def I_point(self) -> Vec3:
        return self._points["I"]

    @property
    def J(self) -> Vec3:
        return self._points["J"]

    def _solve_ad_arc_from_tangent(self) -> ArcGeometry:
        a_x = float(self.A[0])
        a_z = float(self.A[2])
        d_x = float(self.D[0])

        span_x = d_x - a_x
        if abs(span_x) < 1e-8:
            raise ValueError("Chord AD projection on X is too short to construct AD' arc.")

        # AD' central angle.
        phi = float(np.clip(self.params.AD_arc, 1e-4, np.pi - 1e-4))

        # A_tangent is directly the angle(+Z, AD'), so D' is determined by AD x-span.
        a_tangent = float(np.clip(self.params.A_tangent, 1e-4, np.pi - 1e-4))
        sin_beta = math.sin(a_tangent)
        if abs(sin_beta) < 1e-8:
            raise ValueError("A_tangent is too close to 0 or pi; cannot determine D' from AD x-span.")

        d_prime_z = a_z + span_x * (math.cos(a_tangent) / sin_beta)
        d_prime = np.array([d_x, 0.0, d_prime_z], dtype=np.float64)

        # With chord AD' and central angle AD_arc, circle center is on chord bisector.
        chord = d_prime - self.A
        chord_len = float(np.linalg.norm(chord))
        if chord_len < 1e-8:
            raise ValueError("Chord AD' is too short to construct arc geometry.")

        radius = chord_len / (2.0 * math.sin(phi / 2.0))
        if radius <= 1e-8:
            raise ValueError("Computed arc radius is not positive.")

        midpoint = (self.A + d_prime) / 2.0
        perp = np.array([chord[2], 0.0, -chord[0]], dtype=np.float64)
        perp_norm = float(np.linalg.norm(perp))
        if perp_norm < 1e-8:
            raise ValueError("Cannot determine perpendicular bisector for AD' chord.")

        offset = chord_len / (2.0 * math.tan(phi / 2.0))
        center = midpoint + (offset / perp_norm) * perp

        oa = self.A - center
        od = d_prime - center

        normal = np.cross(oa, od)
        normal_norm = float(np.linalg.norm(normal))
        if normal_norm < 1e-8:
            normal = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        else:
            normal = normal / normal_norm

        sweep_angle = float(np.arccos(np.clip(np.dot(oa, od) / (np.linalg.norm(oa) * np.linalg.norm(od)), -1.0, 1.0)))
        arc_points = np.zeros((0, 3), dtype=np.float64)
        for theta in np.linspace(0.0, sweep_angle, 100):
            rot = R.from_rotvec(float(theta) * normal)
            arc_point = center + rot.apply(oa)
            arc_points = np.vstack((arc_points, arc_point))

        return ArcGeometry(
            points=arc_points,
            center=_as_vec3(center, name="arc_center"),
            radius=float(radius),
            normal=_as_vec3(normal, name="arc_normal"),
            end_point=_as_vec3(d_prime, name="arc_end_point"),
        )

    def _rotate_vector(self, vector_origin: ArrayLike, plane_vector: ArrayLike, theta: float) -> Vec3:
        rotation_vector = -theta * np.asarray(plane_vector, dtype=np.float64)
        rotation = R.from_rotvec(rotation_vector)
        return _as_vec3(rotation.apply(np.asarray(vector_origin, dtype=np.float64)), name="rotated_vector")

    def _rotate_points_around_axis(
        self,
        points: ArrayLike,
        axis_center: ArrayLike,
        axis_normal: ArrayLike,
        theta: float,
    ) -> Points3D:
        points_arr = _as_points3d(points, name="points")
        axis_center_arr = _as_vec3(axis_center, name="axis_center")
        axis_normal_arr = _as_vec3(axis_normal, name="axis_normal")
        axis_normal_arr = axis_normal_arr / np.linalg.norm(axis_normal_arr)

        rotation_vector = theta * axis_normal_arr
        rotation = R.from_rotvec(rotation_vector)
        translated_points = points_arr - axis_center_arr
        rotated_points = rotation.apply(translated_points)
        rotated_points += axis_center_arr
        return _as_points3d(rotated_points, name="rotated_points")

    def _line_intersection_with_ad_plane(self, p1: ArrayLike, p2: ArrayLike) -> Vec3 | None:
        a = np.asarray(self.A, dtype=np.float64)
        d = np.asarray(self.D, dtype=np.float64)
        p1_arr = np.asarray(p1, dtype=np.float64)
        p2_arr = np.asarray(p2, dtype=np.float64)

        coeff_a = d[1] - a[1]
        coeff_b = a[0] - d[0]
        coeff_c = coeff_a * a[0] + coeff_b * a[1]

        if np.array_equal(a[:2], d[:2]):
            return None

        denominator = coeff_a * (p2_arr[0] - p1_arr[0]) + coeff_b * (p2_arr[1] - p1_arr[1])
        numerator = coeff_c - coeff_a * p1_arr[0] - coeff_b * p1_arr[1]
        if abs(denominator) < 1e-9:
            return None

        t = numerator / denominator
        intersection_point = p1_arr + t * (p2_arr - p1_arr)
        return _as_vec3(intersection_point, name="intersection_point")

    def _get_ad_arc_point_with_same_xy(self, chord_point_xy: ArrayLike, arc_geometry: ArcGeometry) -> Vec3:
        chord_xy = _as_vec3(chord_point_xy, name="chord_point")
        x = float(chord_xy[0])
        y = float(chord_xy[1])

        dx = x - float(arc_geometry.center[0])
        dy = y - float(arc_geometry.center[1])
        inside = float(arc_geometry.radius**2 - dx**2 - dy**2)
        if inside < 0:
            inside = 0.0

        z = float(arc_geometry.center[2]) + np.sqrt(inside)
        return np.array([x, y, z], dtype=np.float64)

    def _get_circle_3d(self, p1: ArrayLike, p2: ArrayLike, p3: ArrayLike) -> Circle3D:
        p1_arr = _as_vec3(p1, name="p1")
        p2_arr = _as_vec3(p2, name="p2")
        p3_arr = _as_vec3(p3, name="p3")

        v12 = p2_arr - p1_arr
        v13 = p3_arr - p1_arr

        plane_normal = np.cross(v12, v13)
        if np.linalg.norm(plane_normal) < 1e-8:
            raise ValueError("three points are collinear, cannot determine a unique circle")

        mat_a = np.array([v12, v13, plane_normal], dtype=np.float64)
        vec_b = np.array(
            [
                np.dot(v12, (p1_arr + p2_arr) / 2),
                np.dot(v13, (p1_arr + p3_arr) / 2),
                np.dot(plane_normal, p1_arr),
            ],
            dtype=np.float64,
        )

        center = np.linalg.solve(mat_a, vec_b)
        radius = float(np.linalg.norm(center - p1_arr))
        return Circle3D(center=_as_vec3(center, name="circle_center"), radius=radius)

    def _get_sub_arc(self, p1: ArrayLike, p2: ArrayLike, p3: ArrayLike) -> tuple[Points3D, Vec3, float]:
        circle = self._get_circle_3d(p1, p2, p3)
        p1_arr = _as_vec3(p1, name="p1")
        p3_arr = _as_vec3(p3, name="p3")
        oa = p1_arr - circle.center
        od = p3_arr - circle.center
        oa_od_theta = np.arccos(np.clip(np.dot(oa, od) / (np.linalg.norm(oa) * np.linalg.norm(od)), -1.0, 1.0))

        plane_normal = np.cross(oa, od)
        plane_normal = -plane_normal / np.linalg.norm(plane_normal)

        arc_points = np.zeros((0, 3), dtype=np.float64)
        for theta in np.linspace(0.0, float(oa_od_theta), 100):
            ot = self._rotate_vector(oa, plane_normal, float(theta))
            arc_point = circle.center + ot / np.linalg.norm(ot) * circle.radius
            arc_points = np.vstack((arc_points, arc_point))

        return arc_points, circle.center, circle.radius

    def _construct_surface_from_rotated_arc(
        self,
        profile_points: ArrayLike,
        arc_geometry: ArcGeometry,
        total_angle: float,
        num_steps: int = 100,
    ) -> Points3D:
        theta = np.linspace(0.0, float(total_angle), int(num_steps))
        surface_points = np.zeros((0, 3), dtype=np.float64)
        for angle in theta:
            rotated = self._rotate_points_around_axis(
                profile_points,
                arc_geometry.center,
                arc_geometry.normal,
                float(angle),
            )
            surface_points = np.vstack((surface_points, rotated))
        return surface_points

    def _regularize_edge_z(self, torus_points: ArrayLike, bezier_points: ArrayLike) -> Points3D:
        torus = _as_points3d(torus_points, name="torus_points")
        bezier = _as_points3d(bezier_points, name="bezier_points").copy()
        z_values = griddata(torus[:, :2], torus[:, 2], bezier[:, :2], method="cubic")
        bezier[:, 2] = z_values
        return bezier

    def _cut_end_surface(self, surface_points: ArrayLike, contour_points: ArrayLike | None = None) -> Points3D:
        if contour_points is None:
            raise ValueError("contour_points is required for cutting surface")

        contour_points_arr = _as_points3d(contour_points, name="contour_points")
        surface_points_arr = _as_points3d(surface_points, name="surface_points")

        polygon = Polygon(contour_points_arr[:, :2])
        projected_points = surface_points_arr[:, :2]

        clipped: list[Vec3] = []
        for idx, p_2d in enumerate(projected_points):
            if polygon.contains(Point(float(p_2d[0]), float(p_2d[1]))):
                clipped.append(surface_points_arr[idx])

        if not clipped:
            return np.zeros((0, 3), dtype=np.float64)
        return _as_points3d(clipped, name="clipped_surface")

    def _filling_surface(self, arc_geometry: ArcGeometry) -> Points3D:
        num_curve = 100
        num_points_per_curve = 100
        t_values = np.linspace(0.0, 1.0, num_curve)
        angle_margin = float(self.params.AD_arc) / 10.0
        angle_start = -angle_margin
        angle_end = float(self.params.AD_arc) + angle_margin

        gah_control = self.get_curve("AGH").control_points.copy()
        jdi_control = self.get_curve("JDI").control_points.copy()

        # For each corresponding control point pair, only interpolate y/z.
        # x is carried by the base GAH profile, then all points are swept by rotation.
        filling_surface_points = np.zeros((0, 3), dtype=np.float64)
        for tv in t_values:
            control_points = gah_control.copy()
            control_points[:, 1] = (1.0 - tv) * gah_control[:, 1] + tv * jdi_control[:, 1]
            control_points[:, 2] = (1.0 - tv) * gah_control[:, 2] + tv * jdi_control[:, 2]

            # Two-segment quadratic Bezier (matches side-profile window rendering),
            # ensuring the surface passes through A/D'.
            # control_points order: [G, A_P1_G, A, A_P1_H, H]
            half_pts = max(num_points_per_curve // 2, 2)
            curve1 = Bezier(control_points[:3])   # G → A_P1_G → A
            curve2 = Bezier(control_points[2:])   # A → A_P1_H → H
            curve_points = np.vstack((
                curve1.get_points(num_points=half_pts),
                curve2.get_points(num_points=half_pts),
            ))

            angle = float(angle_start + tv * (angle_end - angle_start))
            rotated_curve = self._rotate_points_around_axis(
                curve_points,
                arc_geometry.center,
                arc_geometry.normal,
                angle,
            )
            filling_surface_points = np.vstack((filling_surface_points, rotated_curve))

        return filling_surface_points

    def _fps(self, sample: ArrayLike, num: int) -> tuple[npt.NDArray[np.int_], Points3D]:
        sample_arr = _as_points3d(sample, name="sample")
        n = sample_arr.shape[0]
        if n <= num:
            indices = np.arange(n, dtype=np.int_)
            return indices, sample_arr

        center = np.mean(sample_arr, axis=0)
        dist_to_center_sq = np.sum((sample_arr - center) ** 2, axis=1)
        start_idx = int(np.argmax(dist_to_center_sq))

        selected_indices = np.zeros(num, dtype=np.int_)
        selected_indices[0] = start_idx

        current_point = sample_arr[start_idx]
        min_distances = np.sum((sample_arr - current_point) ** 2, axis=1)

        for i in range(1, num):
            farthest_point_idx = int(np.argmax(min_distances))
            selected_indices[i] = farthest_point_idx

            new_selected_point = sample_arr[farthest_point_idx]
            dist_new = np.sum((sample_arr - new_selected_point) ** 2, axis=1)
            min_distances = np.minimum(min_distances, dist_new)

        return selected_indices, sample_arr[selected_indices]

    def _reconstruct_mesh_from_point_cloud_bpa(self, select_sample: ArrayLike) -> o3d.geometry.TriangleMesh:
        select_sample_arr = _as_points3d(select_sample, name="select_sample")
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(select_sample_arr)

        pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))

        distances = pcd.compute_nearest_neighbor_distance()
        avg_dist = float(np.mean(distances))
        radii = [avg_dist, avg_dist * 2, avg_dist * 4]

        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
            pcd,
            o3d.utility.DoubleVector(radii),
        )

        mesh.remove_degenerate_triangles()
        mesh.remove_unreferenced_vertices()
        mesh.remove_duplicated_triangles()
        mesh.remove_duplicated_vertices()

        triangle_clusters, cluster_n_triangles, _ = mesh.cluster_connected_triangles()
        if len(cluster_n_triangles) > 0:
            triangle_clusters_arr = np.asarray(triangle_clusters)
            cluster_n_triangles_arr = np.asarray(cluster_n_triangles)
            max_cluster_idx = int(cluster_n_triangles_arr.argmax())
            triangles_to_remove = triangle_clusters_arr != max_cluster_idx
            mesh.remove_triangles_by_mask(triangles_to_remove)

        return mesh

    def _apply_final_xy_rotation(self, artifacts: BuildArtifacts) -> BuildArtifacts:
        xy_rotation = float(self.params.xy_rotation)
        if abs(xy_rotation) < 1e-12:
            return artifacts

        # Positive xy_rotation means clockwise on XY plane, so negate around +Z.
        theta = -xy_rotation
        axis_center = np.zeros(3, dtype=np.float64)
        axis_normal = np.array([0.0, 0.0, 1.0], dtype=np.float64)

        def _rotate(points: Points3D) -> Points3D:
            return self._rotate_points_around_axis(points, axis_center, axis_normal, theta)

        rotated_curve_points = {name: _rotate(points) for name, points in artifacts.curve_points.items()}
        rotated_arc_geometry = ArcGeometry(
            points=_rotate(artifacts.arc_geometry.points),
            center=_as_vec3(_rotate(np.asarray([artifacts.arc_geometry.center]))[0], name="rotated_arc_center"),
            radius=artifacts.arc_geometry.radius,
            normal=_as_vec3(
                R.from_euler("z", theta).apply(artifacts.arc_geometry.normal),
                name="rotated_arc_normal",
            ),
            end_point=_as_vec3(_rotate(np.asarray([artifacts.arc_geometry.end_point]))[0], name="rotated_arc_end_point"),
        )

        return BuildArtifacts(
            curve_points=rotated_curve_points,
            abcdef_edge_points=_rotate(artifacts.abcdef_edge_points),
            edge_points=_rotate(artifacts.edge_points),
            bone_points=_rotate(artifacts.bone_points),
            all_curve_points=_rotate(artifacts.all_curve_points),
            filling_surface_points=_rotate(artifacts.filling_surface_points),
            clipped_filling_surface_points=_rotate(artifacts.clipped_filling_surface_points),
            all_filling_surface_points=_rotate(artifacts.all_filling_surface_points),
            mesh_points=_rotate(artifacts.mesh_points),
            arc_geometry=rotated_arc_geometry,
            mesh=artifacts.mesh,
        )

    def _construct_base(self) -> BuildArtifacts:
        curve_points: dict[CurveName, Points3D] = {
            "AB": self.get_curve("AB").get_points(),
            "BC": self.get_curve("BC").get_points(),
            "CD": self.get_curve("CD").get_points(),
            "AF": self.get_curve("AF").get_points(),
            "FE": self.get_curve("FE").get_points(),
            "ED": self.get_curve("ED").get_points(),
            "AGH": self.get_curve("AGH").get_points(),
            "JDI": self.get_curve("JDI").get_points(),
        }

        arc_geometry = self._solve_ad_arc_from_tangent()

        abcdef_edge_points = np.vstack(
            (
                curve_points["AB"],
                curve_points["BC"],
                curve_points["CD"],
                curve_points["ED"][::-1],
                curve_points["FE"][::-1],
                curve_points["AF"][::-1],
            )
        )

        edge_points = np.vstack(
            (
                curve_points["AB"],
                curve_points["BC"],
                curve_points["CD"],
                curve_points["AF"],
                curve_points["FE"],
                curve_points["ED"],
                curve_points["AGH"],
                curve_points["JDI"],
            )
        )
        bone_points = arc_geometry.points
        all_curve_points = np.vstack((edge_points, bone_points))

        filling_surface_points = self._filling_surface(arc_geometry)
        clipped_filling_surface_points = self._cut_end_surface(
            filling_surface_points,
            contour_points=abcdef_edge_points,
        )
        all_filling_surface_points = clipped_filling_surface_points

        _, mesh_points = self._fps(sample=all_filling_surface_points, num=2000)

        artifacts = BuildArtifacts(
            curve_points=curve_points,
            abcdef_edge_points=abcdef_edge_points,
            edge_points=edge_points,
            bone_points=bone_points,
            all_curve_points=all_curve_points,
            filling_surface_points=filling_surface_points,
            clipped_filling_surface_points=clipped_filling_surface_points,
            all_filling_surface_points=all_filling_surface_points,
            mesh_points=mesh_points,
            arc_geometry=arc_geometry,
        )
        artifacts = self._apply_final_xy_rotation(artifacts)
        self.artifacts = artifacts
        return artifacts

    def _construct_mesh(self, artifacts: BuildArtifacts) -> o3d.geometry.TriangleMesh:
        return self._reconstruct_mesh_from_point_cloud_bpa(artifacts.mesh_points)

    def build(self) -> Self:
        artifacts = self._construct_base()
        artifacts.mesh = self._construct_mesh(artifacts)
        self.artifacts = artifacts
        return self

    def _require_artifacts(self) -> BuildArtifacts:
        if self.artifacts is None:
            raise RuntimeError("Call build() before accessing build artifacts.")
        return self.artifacts

    def plot_bone_curve(self, ax) -> None:
        artifacts = self._require_artifacts()
        cp = artifacts.curve_points

        ax.plot(cp["AB"][:, 0], cp["AB"][:, 1], cp["AB"][:, 2], "b-", label="bezier")
        ax.plot(cp["BC"][:, 0], cp["BC"][:, 1], cp["BC"][:, 2], "b-")
        ax.plot(cp["CD"][:, 0], cp["CD"][:, 1], cp["CD"][:, 2], "b-")
        ax.plot(cp["ED"][:, 0], cp["ED"][:, 1], cp["ED"][:, 2], "b-")
        ax.plot(cp["FE"][:, 0], cp["FE"][:, 1], cp["FE"][:, 2], "b-")
        ax.plot(cp["AF"][:, 0], cp["AF"][:, 1], cp["AF"][:, 2], "b-")

        ax.plot(
            artifacts.arc_geometry.points[:, 0],
            artifacts.arc_geometry.points[:, 1],
            artifacts.arc_geometry.points[:, 2],
            "r-",
            label="curve",
        )
        ax.plot(cp["AGH"][:, 0], cp["AGH"][:, 1], cp["AGH"][:, 2], "m-", label="AGH")
        ax.plot(cp["JDI"][:, 0], cp["JDI"][:, 1], cp["JDI"][:, 2], "m-", label="JDI")

        key_points = np.vstack([self.A, self.B, self.C, self.D, self.E, self.F, self.G, self.H, self.I_point, self.J])
        ax.scatter(key_points[:, 0], key_points[:, 1], key_points[:, 2], color="g", s=100)

        ax.scatter(
            artifacts.arc_geometry.center[0],
            artifacts.arc_geometry.center[1],
            artifacts.arc_geometry.center[2],
            color="y",
            s=200,
            label="center",
        )

        labels = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
        for i, label in enumerate(labels):
            ax.text(key_points[i, 0], key_points[i, 1], key_points[i, 2], label)

        self._plot_ax_set(ax)
        ax.set_title("bone curve")

    def plot_regularized_edge(self, ax) -> None:
        artifacts = self._require_artifacts()
        cp = artifacts.curve_points
        ax.plot(cp["AGH"][:, 0], cp["AGH"][:, 1], cp["AGH"][:, 2], "deepskyblue", label="regularized_edge")
        ax.plot(cp["JDI"][:, 0], cp["JDI"][:, 1], cp["JDI"][:, 2], "deepskyblue")
        self._plot_ax_set(ax)
        ax.set_title("regularized edge")

    def plot_end_points(self, ax) -> None:
        artifacts = self._require_artifacts()
        ax.scatter(
            artifacts.clipped_filling_surface_points[:, 0],
            artifacts.clipped_filling_surface_points[:, 1],
            artifacts.clipped_filling_surface_points[:, 2],
            color="purple",
            label="bezier",
            s=0.1,
        )
        self._plot_ax_set(ax)
        ax.set_title("end points")

    def plot_filling_surface(self, ax) -> None:
        artifacts = self._require_artifacts()
        ax.scatter(
            artifacts.filling_surface_points[:, 0],
            artifacts.filling_surface_points[:, 1],
            artifacts.filling_surface_points[:, 2],
            color="orange",
            s=0.1,
        )
        self._plot_ax_set(ax)
        ax.set_title("filling surface")

    def plot_mesh_points(self, ax) -> None:
        artifacts = self._require_artifacts()
        ax.scatter(artifacts.mesh_points[:, 0], artifacts.mesh_points[:, 1], artifacts.mesh_points[:, 2], color="g", s=0.1)
        self._plot_ax_set(ax)
        ax.set_title("mesh points")

    def plot_xy_plane(self, ax) -> None:
        artifacts = self._require_artifacts()
        ax.scatter(
            artifacts.all_filling_surface_points[:, 0],
            artifacts.all_filling_surface_points[:, 1],
            color="orange",
            s=10,
            label="filling surface points",
        )
        self._plot_ax_set(ax)
        ax.set_title("xy plane")

    def _plot_ax_set(self, ax) -> None:
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        if ax.name == "3d":
            ax.set_zlabel("Z")
            ax.set_zlim(-10, 10)
        ax.legend()
        ax.set_xlim(-5, 15)
        ax.set_ylim(-10, 10)
        ax.set_aspect("equal")

    def get_bone_points(self) -> Points3D:
        return self._require_artifacts().all_curve_points

    def get_surface_points(self) -> Points3D:
        return self._require_artifacts().all_filling_surface_points

    def save_mesh(self, output_path: str) -> None:
        artifacts = self._require_artifacts()
        if artifacts.mesh is None:
            raise RuntimeError("Call build() before save_mesh().")
        o3d.io.write_triangle_mesh(output_path, artifacts.mesh)