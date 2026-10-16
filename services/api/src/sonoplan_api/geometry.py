"""Floor contour geometry checks (mirror of packages/domain geometry)."""

from __future__ import annotations

from typing import Any

EPS = 1e-9


def _vertex_eq(a: dict[str, float], b: dict[str, float]) -> bool:
    return abs(a["x"] - b["x"]) <= EPS and abs(a["y"] - b["y"]) <= EPS


def strip_closing_duplicate(contour: list[dict[str, float]]) -> list[dict[str, float]]:
    if len(contour) >= 2 and _vertex_eq(contour[0], contour[-1]):
        return contour[:-1]
    return list(contour)


def is_contour_explicitly_closed(contour: list[dict[str, float]]) -> bool:
    if len(contour) < 4:
        return False
    if not _vertex_eq(contour[0], contour[-1]):
        return False
    return len(strip_closing_duplicate(contour)) >= 3


def _cross(o: dict, a: dict, b: dict) -> float:
    return (a["x"] - o["x"]) * (b["y"] - o["y"]) - (a["y"] - o["y"]) * (b["x"] - o["x"])


def _on_segment(a: dict, b: dict, p: dict) -> bool:
    return (
        min(a["x"], b["x"]) - EPS <= p["x"] <= max(a["x"], b["x"]) + EPS
        and min(a["y"], b["y"]) - EPS <= p["y"] <= max(a["y"], b["y"]) + EPS
    )


def _segments_intersect(a: dict, b: dict, c: dict, d: dict) -> bool:
    d1 = _cross(a, b, c)
    d2 = _cross(a, b, d)
    d3 = _cross(c, d, a)
    d4 = _cross(c, d, b)
    if ((d1 > EPS and d2 < -EPS) or (d1 < -EPS and d2 > EPS)) and (
        (d3 > EPS and d4 < -EPS) or (d3 < -EPS and d4 > EPS)
    ):
        return True
    if abs(d1) <= EPS and _on_segment(a, b, c):
        return True
    if abs(d2) <= EPS and _on_segment(a, b, d):
        return True
    if abs(d3) <= EPS and _on_segment(c, d, a):
        return True
    if abs(d4) <= EPS and _on_segment(c, d, b):
        return True
    return False


def find_self_intersections(contour: list[dict[str, float]]) -> list[dict[str, Any]]:
    ring = strip_closing_duplicate(contour)
    n = len(ring)
    if n < 3:
        return []
    errors: list[dict[str, Any]] = []
    for i in range(n):
        a = ring[i]
        b = ring[(i + 1) % n]
        for j in range(i + 1, n):
            adjacent = j == i or (j + 1) % n == i or i + 1 == j or (i == 0 and j == n - 1)
            if adjacent:
                continue
            c = ring[j]
            d = ring[(j + 1) % n]
            if _segments_intersect(a, b, c, d):
                errors.append(
                    {
                        "code": "contour_self_intersection",
                        "message": f"Floor contour self-intersects at edges {i} and {j}",
                        "segmentIndexA": i,
                        "segmentIndexB": j,
                    }
                )
    return errors


def validate_floor_contour(contour: list[dict[str, float]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    unique = strip_closing_duplicate(contour)
    if len(unique) < 3:
        errors.append(
            {
                "code": "too_few_vertices",
                "message": "Floor contour needs at least 3 distinct vertices",
            }
        )
        return errors
    if not is_contour_explicitly_closed(contour):
        errors.append(
            {
                "code": "contour_not_closed",
                "message": "Floor contour must be explicitly closed (first vertex equals last)",
            }
        )
    errors.extend(find_self_intersections(contour))
    return errors


def point_in_polygon(point: dict[str, float], contour: list[dict[str, float]]) -> bool:
    ring = strip_closing_duplicate(contour)
    n = len(ring)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        yi, yj = ring[i]["y"], ring[j]["y"]
        xi, xj = ring[i]["x"], ring[j]["x"]
        denom = (yj - yi) if (yj - yi) != 0 else EPS
        if (yi > point["y"]) != (yj > point["y"]) and point["x"] < ((xj - xi) * (point["y"] - yi)) / denom + xi:
            inside = not inside
        j = i
    return inside
