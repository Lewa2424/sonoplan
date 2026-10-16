"""Model validation: errors (blocking) and warnings."""

from __future__ import annotations

from typing import Any

from sonoplan_api.geometry import point_in_polygon, validate_floor_contour


def _source_has_usable_spectrum(source: dict[str, Any]) -> bool:
    spectrum = source.get("powerSpectrumLw") or []
    if not spectrum:
        return False
    for band in spectrum:
        level = band.get("level") or {}
        value = level.get("value")
        if value is not None and isinstance(value, (int, float)) and value == value:  # not NaN
            return True
    return False


def _source_inside_solid(source: dict[str, Any], solids: list[dict[str, Any]]) -> dict[str, str] | None:
    pos = source.get("position") or {}
    px, py, pz = pos.get("x"), pos.get("y"), pos.get("z")
    if px is None or py is None or pz is None:
        return None
    for solid in solids:
        height = (solid.get("heightM") or {}).get("value")
        if height is None or not isinstance(height, (int, float)) or height <= 0:
            continue
        base = solid.get("baseZM", 0)
        contour = solid.get("floorContour") or []
        if point_in_polygon({"x": float(px), "y": float(py)}, contour):
            if float(base) - 1e-9 <= float(pz) <= float(base) + float(height) + 1e-9:
                return {"solidId": str(solid.get("id", "")), "solidName": str(solid.get("name", ""))}
    return None


def validate_model(snapshot: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for room in snapshot.get("rooms") or []:
        room_id = room.get("id")
        contour = room.get("floorContour") or []
        for ce in validate_floor_contour(contour):
            errors.append(
                {
                    "code": ce["code"],
                    "severity": "error",
                    "message": ce["message"],
                    "path": f"rooms/{room_id}/floorContour",
                    "entityId": room_id,
                }
            )
        height = (room.get("heightM") or {}).get("value")
        if height is None:
            errors.append(
                {
                    "code": "room_height_unknown",
                    "severity": "error",
                    "message": (room.get("heightM") or {}).get("nullReason")
                    or "Room height is unknown (null ≠ 0)",
                    "path": f"rooms/{room_id}/heightM",
                    "entityId": room_id,
                }
            )

    solids = snapshot.get("solids") or []
    for source in snapshot.get("sources") or []:
        source_id = source.get("id")
        for band in source.get("powerSpectrumLw") or []:
            unit = (band.get("level") or {}).get("unit")
            if unit is not None and unit != "dB":
                errors.append(
                    {
                        "code": "source_spectrum_not_lw",
                        "severity": "error",
                        "message": f"Source spectrum must be Lw (unit dB), got {unit}; Lw ≠ Lp",
                        "path": f"sources/{source_id}/powerSpectrumLw",
                        "entityId": source_id,
                    }
                )
                break
        if not _source_has_usable_spectrum(source):
            errors.append(
                {
                    "code": "source_spectrum_missing",
                    "severity": "error",
                    "message": "Source has no usable Lw spectrum bands",
                    "path": f"sources/{source_id}/powerSpectrumLw",
                    "entityId": source_id,
                }
            )
        hit = _source_inside_solid(source, solids)
        if hit:
            errors.append(
                {
                    "code": "source_inside_solid",
                    "severity": "error",
                    "message": f'Source is inside solid "{hit["solidName"]}"',
                    "path": f"sources/{source_id}/position",
                    "entityId": source_id,
                }
            )

    for material in snapshot.get("materials") or []:
        if material.get("estimated"):
            mid = material.get("id")
            warnings.append(
                {
                    "code": "material_estimated",
                    "severity": "warning",
                    "message": f'Material "{material.get("name")}" uses estimated properties',
                    "path": f"materials/{mid}",
                    "entityId": mid,
                }
            )

    return {"errors": errors, "warnings": warnings}
