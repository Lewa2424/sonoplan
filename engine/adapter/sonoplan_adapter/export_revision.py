"""Build SPPS workdir from a SonoPlan revision snapshot (Phase 2A: AABB box).

Irregular contours use the bounding box of the floor contour — honest note
in the returned meta. Full polygon extrusion + TetGen is a later stage.
"""

from __future__ import annotations

import json
import math
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cbin_io import scale_cbin_file_inplace
from .mbin_io import scale_mbin_file_inplace

FREQS = [
    20000, 16000, 12500, 10000, 8000, 6300, 5000, 4000, 3150, 2500, 2000,
    1600, 1250, 1000, 800, 630, 500, 400, 315, 250, 200, 160, 125, 100, 80,
    63, 50,
]
# Octaves of the model spectrum (apps/web STANDARD_BANDS_HZ); dBA needs all of them.
CALC_BANDS = {63, 125, 250, 500, 1000, 2000, 4000, 8000}
REF_CUBE_M = 5.0
# SPPS keeps cells × time steps × bands × coupes in RAM; cap the cut-map size.
MAX_COUPE_CELLS = 20_000
# SPPS links a tetra to the coupe only if a tetra edge pierces the parallelogram
# strictly inside (float32, u/v in [0,1)). Room-sized coupe edges lie exactly on
# the walls, so tetras whose plane section touches only wall edges were never
# linked and got no cut-map energy (wedge-shaped empty zones). Overhang fixes it.
COUPE_WALL_OVERHANG_M = 0.01
PROBE_COUPE_XML_ID = 7002


@dataclass(frozen=True)
class ExportMeta:
    width_m: float
    depth_m: float
    height_m: float
    origin_x: float
    origin_y: float
    exact_rectangle: bool
    source_count: int
    workplace_count: int
    notes: tuple[str, ...]


def _f(v: float) -> str:
    return f"{float(v):.6g}"


def room_aabb(snapshot: dict[str, Any]) -> tuple[float, float, float, float, float, bool]:
    """Return (min_x, min_y, width, depth, height, exact_rectangle)."""
    rooms = snapshot.get("rooms") or []
    if not rooms:
        raise ValueError("snapshot has no rooms")
    room = rooms[0]
    height = float((room.get("heightM") or {}).get("value") or 0)
    if height <= 0:
        raise ValueError("room heightM must be > 0")
    contour = room.get("floorContour") or []
    # Drop closing duplicate
    pts: list[tuple[float, float]] = []
    for p in contour:
        xy = (float(p["x"]), float(p["y"]))
        if pts and abs(pts[0][0] - xy[0]) < 1e-9 and abs(pts[0][1] - xy[1]) < 1e-9:
            continue
        pts.append(xy)
    if len(pts) < 3:
        raise ValueError("floorContour needs >= 3 vertices")
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    depth = max_y - min_y
    if width < 0.5 or depth < 0.5:
        raise ValueError("room plan AABB too small (<0.5 m)")
    exact = _is_axis_aligned_rectangle(pts, min_x, min_y, max_x, max_y)
    return min_x, min_y, width, depth, height, exact


def _is_axis_aligned_rectangle(
    pts: list[tuple[float, float]],
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
) -> bool:
    if len(pts) != 4:
        return False
    corners = {
        (min_x, min_y),
        (max_x, min_y),
        (max_x, max_y),
        (min_x, max_y),
    }
    tol = 1e-4
    for x, y in pts:
        if not any(abs(x - cx) < tol and abs(y - cy) < tol for cx, cy in corners):
            return False
    return True


def _absorption_by_band_from_snapshot(
    snapshot: dict[str, Any],
) -> dict[str, float]:
    """Map bandHz → α from room material; empty → caller uses default."""
    rooms = snapshot.get("rooms") or []
    materials = snapshot.get("materials") or []
    if not rooms or not materials:
        return {}
    mat_id = rooms[0].get("materialVersionId")
    mat = None
    for m in materials:
        if m.get("id") == mat_id:
            mat = m
            break
    if mat is None:
        mat = materials[0]
    out: dict[str, float] = {}
    for band in mat.get("absorptionByBand") or []:
        hz = int(band.get("bandHz") or 0)
        alpha = band.get("alpha")
        if hz and alpha is not None:
            out[str(hz)] = float(alpha)
    return out


def compact_export_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Small JSON for GitHub Actions workflow_dispatch input."""
    min_x, min_y, width, depth, height, exact = room_aabb(snapshot)
    sources = []
    for s in snapshot.get("sources") or []:
        pos = s.get("position") or {}
        lw: dict[str, float] = {}
        for band in s.get("powerSpectrumLw") or []:
            hz = int(band.get("bandHz") or 0)
            level = (band.get("level") or {}).get("value")
            if hz and level is not None:
                lw[str(hz)] = float(level)
        sources.append(
            {
                "id": s.get("id"),
                "name": s.get("name") or "src",
                "x": float(pos.get("x") or 0) - min_x,
                "y": float(pos.get("y") or 0) - min_y,
                "z": float(pos.get("z") or 0),
                "lwByBand": lw,
            }
        )
    workplaces = []
    wp_zs: list[float] = []
    for w in snapshot.get("workplaces") or []:
        pos = w.get("position") or {}
        rh = float((w.get("receiverHeightM") or {}).get("value") or 1.5)
        z = float(pos.get("z") or 0)
        # Receiver height above floor if z≈0
        recv_z = z if z > 0.05 else rh
        wp_zs.append(recv_z)
        workplaces.append(
            {
                "id": w.get("id"),
                "name": w.get("name") or "wp",
                "x": float(pos.get("x") or 0) - min_x,
                "y": float(pos.get("y") or 0) - min_y,
                "z": recv_z,
            }
        )
    source_zs = [float(s["z"]) for s in sources]
    coupe_z = _coupe_z_away_from_sources(
        preferred_z=(sum(wp_zs) / len(wp_zs) if wp_zs else 1.5),
        source_zs=source_zs,
        height_m=height,
    )
    solids = snapshot.get("solids") or []
    return {
        "schemaVersion": "1.0",
        "box": {
            "widthM": width,
            "depthM": depth,
            "heightM": height,
            "originX": min_x,
            "originY": min_y,
            "exactRectangle": exact,
        },
        "sources": sources,
        "workplaces": workplaces,
        "absorptionByBand": _absorption_by_band_from_snapshot(snapshot),
        "coupeZM": coupe_z,
        "solidCount": len(solids),
    }


def _coupe_z_away_from_sources(
    *,
    preferred_z: float,
    source_zs: list[float],
    height_m: float,
    min_sep_m: float = 0.35,
) -> float:
    """Cutting plane must not sit on source Z — coplanar start → almost no crossings."""
    lo, hi = 0.15, max(height_m - 0.15, 0.2)
    preferred = min(max(preferred_z, lo), hi)
    candidates = [
        preferred,
        preferred - min_sep_m,
        preferred + min_sep_m,
        preferred - 2 * min_sep_m,
        preferred + 2 * min_sep_m,
        1.2,
        1.8,
        lo + 0.1,
        hi - 0.1,
    ]
    for z in candidates:
        zc = min(max(z, lo), hi)
        if not source_zs:
            return zc
        if all(abs(zc - sz) >= min_sep_m for sz in source_zs):
            return zc
    # Last resort: midway between floor and lowest source
    lowest = min(source_zs) if source_zs else preferred
    return min(max(lowest - min_sep_m, lo), hi)


def coupe_resolution_m(width: float, depth: float) -> float:
    """Cut-map cell ~1/80 of the shorter side in [0.125, 0.25] m, ≤ MAX_COUPE_CELLS."""
    res = min(0.25, max(0.125, min(width, depth) / 80.0))
    return max(res, math.sqrt(width * depth / MAX_COUPE_CELLS))


def _lw_for_freq(lw_by_band: dict[str, float], freq: int) -> float:
    if str(freq) in lw_by_band:
        return float(lw_by_band[str(freq)])
    if not lw_by_band:
        # Quiet fallback — still finite; prefer user bands
        return 70.0 if freq in CALC_BANDS else 60.0
    # nearest band
    keys = sorted(int(k) for k in lw_by_band.keys())
    nearest = min(keys, key=lambda k: abs(k - freq))
    return float(lw_by_band[str(nearest)])


def _alpha_for_freq(absorb_by_band: dict[str, float], freq: int) -> float:
    if str(freq) in absorb_by_band:
        return float(absorb_by_band[str(freq)])
    if not absorb_by_band:
        return 0.02
    keys = sorted(int(k) for k in absorb_by_band.keys())
    nearest = min(keys, key=lambda k: abs(k - freq))
    return float(absorb_by_band[str(nearest)])


def _bfreq_absorb(absorb_by_band: dict[str, float]) -> list[ET.Element]:
    nodes: list[ET.Element] = []
    for freq in FREQS:
        el = ET.Element("bfreq")
        el.set("freq", str(freq))
        el.set("absorb", _f(_alpha_for_freq(absorb_by_band, freq)))
        el.set("diffusion", "0")
        el.set("loi", "0")
        nodes.append(el)
    return nodes


def build_config_xml(payload: dict[str, Any]) -> ET.ElementTree:
    box = payload["box"]
    width = float(box["widthM"])
    depth = float(box["depthM"])
    height = float(box["heightM"])
    sources = list(payload.get("sources") or [])
    workplaces = list(payload.get("workplaces") or [])
    if not sources:
        raise ValueError("export needs at least one source")
    if not workplaces:
        raise ValueError("export needs at least one workplace (punctual receiver)")

    # Keep receivers inside the box with a margin
    def _clamp(x: float, y: float, z: float) -> tuple[float, float, float]:
        m = 0.05
        return (
            min(max(x, m), width - m),
            min(max(y, m), depth - m),
            min(max(z, m), height - m),
        )

    root = ET.Element("configuration")
    root.set("workingdirectory", "./")
    sim = ET.SubElement(root, "simulation")
    for k, v in {
        # Trailing slash required: SPPS concatenates folder+"Global/"+file
        # without an extra separator (upstream configs use recepteurss\).
        "recepteurss_directory": "recepteurss/",
        "recepteurss_filename": "Sound_level.csbin",
        "recepteurss_cut_filename": "rs_cut.csbin",
        "receiversp_directory": "Punctual receivers",
        "receiversp_filename": "Sound level.recp",
        "receiversp_filename_adv": "Advanced sound level.gap",
        "cumul_filename": "Total energy.recp",
        "modelName": "mesh.cbin",
        "tetrameshFileName": "tetramesh.mbin",
        "abs_atmo_calc": "1",
        "enc_calc": "0",
        "trans_calc": "0",
        "direct_calc": "0",
        "duree_simulation": "0.5",
        "output_recp_bysource": "0",
        # Per-band cut files → A-weighting once per band in decode.
        "output_recs_byfreq": "1",
        "surf_receiv_method": "0",
        "random_seed": "1",
        "computation_method": "1",
        "nbparticules": "40000",
        "nbparticules_rendu": "0",
        "pasdetemps": "5e-4",
        "rayon_recepteurp": _f(min(1.0, 0.1 * min(width, depth, height))),
        "trans_epsilon": "5",
        "intensity_filename": "Intensity vector.rpi",
        "intensity_folder": "IntensityAnimation",
        "intensity_rp_filename": "ponct_intensity.gabe",
        "stats_filename": "statsSPPS.gabe",
        "particules_directory": "particles/",
        "particules_filename": "particles.pbin",
        "directivities_directory": "",
    }.items():
        sim.set(k, str(v))

    freq_enum = ET.SubElement(sim, "freq_enum")
    for freq in FREQS:
        bf = ET.SubElement(freq_enum, "bfreq")
        bf.set("freq", str(freq))
        bf.set("docalc", "1" if freq in CALC_BANDS else "0")

    atm = ET.SubElement(root, "condition_atmospherique")
    for k, v in {
        "absatmo": "0",
        "disable_absatmo_computation": "0",
        "humidite": "50",
        "pression": "101325",
        "alog": "0",
        "blin": "0",
        "lst_soltype": "1",
        "z0": "0.02",
        "temperature": "20",
    }.items():
        atm.set(k, v)

    absorb_by_band = dict(payload.get("absorptionByBand") or {})
    mats = ET.SubElement(root, "surface_absorption_enum")
    ts = ET.SubElement(mats, "type_surface")
    ts.set("id", "0")
    ts.set("resistivite", "100")
    ts.set("side_material", "1")
    for child in _bfreq_absorb(absorb_by_band):
        ts.append(child)

    ET.SubElement(root, "subdomains")
    sources_el = ET.SubElement(root, "sources")
    for i, s in enumerate(sources):
        x, y, z = _clamp(float(s["x"]), float(s["y"]), float(s["z"]))
        el = ET.SubElement(sources_el, "source")
        el.set("id", str(5000 + i))
        el.set("name", str(s.get("name") or f"src_{i}"))
        el.set("directivity_file", "")
        el.set("x", _f(x))
        el.set("y", _f(y))
        el.set("z", _f(z))
        el.set("delay", "0")
        el.set("u", "1")
        el.set("v", "0")
        el.set("w", "0")
        el.set("directivite", "0")
        lw = s.get("lwByBand") or {}
        for freq in FREQS:
            bf = ET.SubElement(el, "bfreq")
            bf.set("freq", str(freq))
            bf.set("db", _f(_lw_for_freq(lw, freq)))

    rec_el = ET.SubElement(root, "recepteursp")
    for i, w in enumerate(workplaces):
        x, y, z = _clamp(float(w["x"]), float(w["y"]), float(w["z"]))
        el = ET.SubElement(rec_el, "recepteur_ponctuel")
        el.set("id", str(6000 + i))
        name = str(w.get("name") or f"wp_{i}")
        # SPPS folder name from lbl/name — keep filesystem-safe
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)[
            :40
        ] or f"wp_{i}"
        el.set("name", safe)
        el.set("lbl", safe)
        el.set("x", _f(x))
        el.set("y", _f(y))
        el.set("z", _f(z))
        el.set("u", "-1")
        el.set("v", "0")
        el.set("w", "0")
        for freq in FREQS:
            bf = ET.SubElement(el, "bfreq")
            bf.set("freq", str(freq))
            bf.set("db", "-200")

    # Horizontal cutting plane — keep clear of source Z (crossing-based deposit).
    coupe_z = float(payload.get("coupeZM") or 1.5)
    source_zs = [float(s.get("z") or 0) for s in sources]
    coupe_z = _coupe_z_away_from_sources(
        preferred_z=coupe_z, source_zs=source_zs, height_m=height
    )
    coupe_z = min(max(coupe_z, 0.1), height - 0.05)
    payload["coupeZM"] = coupe_z
    resolution = coupe_resolution_m(width, depth)
    recepteurss = ET.SubElement(root, "recepteurss")
    coupe = ET.SubElement(recepteurss, "recepteur_surfacique_coupe")
    coupe.set("id", "7001")
    coupe.set("name", "plan_coupe")
    # Rectangle A—B—C in SPPS coords (origin at room AABB min), overhanging walls.
    # B = (-m,-m,z), A = (-m,depth+m,z), C = (width+m,-m,z) → BA +Y, BC +X.
    m = COUPE_WALL_OVERHANG_M
    coupe.set("ax", _f(-m))
    coupe.set("ay", _f(depth + m))
    coupe.set("az", _f(coupe_z))
    coupe.set("bx", _f(-m))
    coupe.set("by", _f(-m))
    coupe.set("bz", _f(coupe_z))
    coupe.set("cx", _f(width + m))
    coupe.set("cy", _f(-m))
    coupe.set("cz", _f(coupe_z))
    coupe.set("resolution", _f(resolution))

    # Diagnostic mirror of plan_coupe (never the plan map): B in the far
    # corner, BC along −X, BA along −Y. A cell-index bias relative to B shows
    # up mirrored here; a particle-position bias does not. Drop once the
    # plan_coupe corner compression (2/3 of room) is explained.
    probe = ET.SubElement(recepteurss, "recepteur_surfacique_coupe")
    probe.set("id", str(PROBE_COUPE_XML_ID))
    probe.set("name", "probe_coupe_mirror")
    probe.set("ax", _f(width + m))
    probe.set("ay", _f(-m))
    probe.set("az", _f(coupe_z))
    probe.set("bx", _f(width + m))
    probe.set("by", _f(depth + m))
    probe.set("bz", _f(coupe_z))
    probe.set("cx", _f(-m))
    probe.set("cy", _f(depth + m))
    probe.set("cz", _f(coupe_z))
    probe.set("resolution", _f(resolution))

    return ET.ElementTree(root)


def write_spps_workdir(
    *,
    payload: dict[str, Any],
    out_dir: Path,
    fixture_inputs: Path,
) -> ExportMeta:
    """Materialize mesh.cbin / tetramesh.mbin / config.xml / speaker into out_dir."""
    box = payload["box"]
    width = float(box["widthM"])
    depth = float(box["depthM"])
    height = float(box["heightM"])
    exact = bool(box.get("exactRectangle"))
    out_dir.mkdir(parents=True, exist_ok=True)

    template_cbin = fixture_inputs / "mesh.cbin"
    template_mbin = fixture_inputs / "tetramesh.mbin"
    speaker = fixture_inputs / "speaker-test3.txt"
    if not template_cbin.is_file() or not template_mbin.is_file():
        raise FileNotFoundError(f"fixture inputs missing under {fixture_inputs}")

    # In-place float patch of official cube binaries (preserve pad/groupName).
    # Full rewrite via write_cbin zeroed those bytes and led to SPPS SIGSEGV (-11)
    # after "mesh loaded successfully" when loading tetramesh.
    scale_cbin_file_inplace(
        template_cbin,
        out_dir / "mesh.cbin",
        width_m=width,
        depth_m=depth,
        height_m=height,
        ref_size=REF_CUBE_M,
    )
    scale_mbin_file_inplace(
        template_mbin,
        out_dir / "tetramesh.mbin",
        width_m=width,
        depth_m=depth,
        height_m=height,
        ref_size=REF_CUBE_M,
    )

    tree = build_config_xml(payload)
    tree.write(out_dir / "config.xml", encoding="utf-8", xml_declaration=True)
    if speaker.is_file():
        shutil.copy2(speaker, out_dir / "speaker-test3.txt")

    notes = [
        "Phase 2A: SPPS box mesh scaled in-place from official cube cbin/mbin to room AABB.",
        f"Box {width:.3g}×{depth:.3g}×{height:.3g} m; sources/workplaces from revision.",
        (
            f"Horizontal coupe at z={float(payload.get('coupeZM') or 0):.2f} m "
            "(offset from source Z so SPPS can record plane crossings)."
        ),
        (
            "SPPS bands: octaves "
            + ", ".join(str(f) for f in sorted(CALC_BANDS))
            + " Hz; cut map saved per band for dBA (A-weighting once per band)."
        ),
    ]
    if payload.get("absorptionByBand"):
        notes.append("Surface absorption α from revision materials (estimated catalog OK).")
    else:
        notes.append("Surface absorption default α=0.02 (no material on revision).")
    solid_count = int(payload.get("solidCount") or 0)
    if solid_count > 0:
        notes.append(
            f"{solid_count} solid(s) in model — not in SPPS mesh yet "
            "(TetGen/encombrement later; not claimed in this run)."
        )
    if not exact:
        notes.append(
            "Floor contour is not an axis-aligned rectangle — used AABB "
            "(not full polygon extrusion; TetGen later)."
        )
    return ExportMeta(
        width_m=width,
        depth_m=depth,
        height_m=height,
        origin_x=float(box.get("originX") or 0),
        origin_y=float(box.get("originY") or 0),
        exact_rectangle=exact,
        source_count=len(payload.get("sources") or []),
        workplace_count=len(payload.get("workplaces") or []),
        notes=tuple(notes),
    )


def write_export_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )


def load_export_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
