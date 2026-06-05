"""Tests for the Blender-independent raytracing core.

Runs without Blender. Execute with: python -m pytest tests/

The actual ``scene.ray_cast`` is replaced by a fake ray caster against a flat
wall, which lets the whole scatter-point extraction be exercised here.
"""

import math

import numpy as np
import pytest

from core.raytracing import (
    ObjectMotion,
    RadarPose,
    RayHit,
    extract_scatter_points,
    fan_directions,
    line_of_sight,
    radial_velocity,
    rigid_point_velocity,
)


def _translation(vec):
    m = np.eye(4)
    m[:3, 3] = vec
    return m


def _rotation_z(angle):
    c, s = math.cos(angle), math.sin(angle)
    m = np.eye(4)
    m[0, 0], m[0, 1] = c, -s
    m[1, 0], m[1, 1] = s, c
    return m


def _forward_pose():
    """Radar at the origin looking down +X, up is +Z, right is -Y."""
    return RadarPose(
        origin=[0.0, 0.0, 0.0],
        forward=[1.0, 0.0, 0.0],
        right=[0.0, -1.0, 0.0],
        up=[0.0, 0.0, 1.0],
    )


def _wall_caster(distance):
    """Fake ray caster: a wall perpendicular to +X at x == distance."""

    def ray_cast(origin, direction):
        dx = direction[0]
        if dx <= 1e-9:
            return None
        t = (distance - origin[0]) / dx
        location = np.asarray(origin, dtype=np.float64) + t * direction
        return RayHit(
            location=location,
            normal=np.array([-1.0, 0.0, 0.0]),
            object_name="wall",
        )

    return ray_cast


# --- fan_directions ---------------------------------------------------------


def test_fan_directions_count_and_center():
    pose = _forward_pose()
    dirs, az, el = fan_directions(pose, math.radians(60), math.radians(40), 5, 3)
    assert dirs.shape == (15, 3)
    assert az.shape == (15,)
    # Every direction is unit length.
    assert np.allclose(np.linalg.norm(dirs, axis=1), 1.0)
    # The center ray (az=0, el=0) points along the boresight.
    center = dirs[np.argmin(np.abs(az) + np.abs(el))]
    assert np.allclose(center, pose.forward)


def test_fan_directions_edge_angle():
    pose = _forward_pose()
    fov = math.radians(60)
    dirs, az, el = fan_directions(pose, fov, 0.0, 3, 1)
    # The extreme azimuth ray makes fov/2 with the boresight.
    edge = dirs[np.argmax(az)]
    cos_angle = float(np.dot(edge, pose.forward))
    assert math.isclose(cos_angle, math.cos(fov / 2), abs_tol=1e-9)


def test_fan_directions_single_ray_on_boresight():
    pose = _forward_pose()
    dirs, az, el = fan_directions(pose, math.radians(60), math.radians(60), 1, 1)
    assert dirs.shape == (1, 3)
    assert az[0] == 0.0 and el[0] == 0.0
    assert np.allclose(dirs[0], pose.forward)


def test_fan_directions_rejects_zero_counts():
    pose = _forward_pose()
    with pytest.raises(ValueError):
        fan_directions(pose, 1.0, 1.0, 0, 1)


# --- line_of_sight / radial_velocity ---------------------------------------


def test_line_of_sight():
    los, rng = line_of_sight([0, 0, 0], [3, 4, 0])
    assert math.isclose(rng, 5.0)
    assert np.allclose(los, [0.6, 0.8, 0.0])


def test_radial_velocity_receding_is_positive():
    los = np.array([1.0, 0.0, 0.0])
    assert radial_velocity(los, [2.0, 0.0, 0.0]) > 0


def test_radial_velocity_approaching_is_negative():
    los = np.array([1.0, 0.0, 0.0])
    assert radial_velocity(los, [-2.0, 0.0, 0.0]) < 0


def test_radial_velocity_subtracts_radar_motion():
    los = np.array([1.0, 0.0, 0.0])
    # Target and radar move together: no relative range change.
    v = radial_velocity(los, [3.0, 0.0, 0.0], radar_velocity=[3.0, 0.0, 0.0])
    assert math.isclose(v, 0.0)


# --- rigid_point_velocity ---------------------------------------------------


def test_rigid_point_velocity_translation():
    dt = 0.5
    speed = 4.0  # along +X per second
    motion = ObjectMotion(
        current=np.eye(4),
        previous=_translation([-speed * dt, 0, 0]),
        next_=_translation([speed * dt, 0, 0]),
    )
    v = rigid_point_velocity(motion, [1.0, 2.0, 3.0], dt)
    assert np.allclose(v, [speed, 0, 0])


def test_rigid_point_velocity_rotation():
    dt = 1e-3
    omega = 2.0  # rad/s about Z
    motion = ObjectMotion(
        current=np.eye(4),
        previous=_rotation_z(-omega * dt),
        next_=_rotation_z(omega * dt),
    )
    # Point on +X axis: tangential velocity is omega * r along +Y.
    v = rigid_point_velocity(motion, [1.0, 0.0, 0.0], dt)
    assert np.allclose(v, [0.0, omega, 0.0], atol=1e-3)


def test_rigid_point_velocity_static_when_no_neighbors():
    motion = ObjectMotion(current=np.eye(4))
    v = rigid_point_velocity(motion, [1.0, 0.0, 0.0], 0.5)
    assert np.allclose(v, 0.0)


# --- extract_scatter_points -------------------------------------------------


def test_extract_static_wall():
    pose = _forward_pose()
    distance = 10.0
    points = extract_scatter_points(
        pose,
        _wall_caster(distance),
        object_motion={},
        fov_az=math.radians(20),
        fov_el=math.radians(20),
        n_az=4,
        n_el=4,
        dt_seconds=1.0,
    )
    assert len(points) == 16
    # The boresight ray hits the wall at exactly the wall distance; off-axis
    # rays travel slightly further.
    assert min(p.range for p in points) >= distance - 1e-9
    # A static wall has zero radial velocity.
    assert all(math.isclose(p.radial_velocity, 0.0, abs_tol=1e-9) for p in points)
    assert all(p.object_name == "wall" for p in points)


def test_extract_moving_wall_radial_velocity():
    pose = _forward_pose()
    distance = 10.0
    dt = 0.5
    speed = 3.0  # wall moving away along +X
    motion = {
        "wall": ObjectMotion(
            current=np.eye(4),
            previous=_translation([-speed * dt, 0, 0]),
            next_=_translation([speed * dt, 0, 0]),
        )
    }
    points = extract_scatter_points(
        pose,
        _wall_caster(distance),
        object_motion=motion,
        fov_az=0.0,
        fov_el=0.0,
        n_az=1,
        n_el=1,
        dt_seconds=dt,
    )
    assert len(points) == 1
    # Boresight ray, wall receding along the line of sight: +speed.
    assert math.isclose(points[0].radial_velocity, speed, rel_tol=1e-6)


def test_extract_respects_max_range():
    pose = _forward_pose()
    points = extract_scatter_points(
        pose,
        _wall_caster(50.0),
        object_motion={},
        fov_az=math.radians(10),
        fov_el=math.radians(10),
        n_az=3,
        n_el=3,
        dt_seconds=1.0,
        max_range=20.0,
    )
    assert points == []
