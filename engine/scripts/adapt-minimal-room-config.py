#!/usr/bin/env python3
"""Adapt upstream I-Simpa SPPS test config for SonoPlan minimal_room fixture.

Source: src/spps/tests/config.xml at the pinned I-Simpa commit.
Mesh:   src/python_bindings/tests/mesh.cbin + tetramesh.mbin (20x30x10 m,
        material ids 100/101, no surface receivers).

Does not invent acoustic dB values. Numeric locale: dots (ENG-007).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


FREQS = [
    20000,
    16000,
    12500,
    10000,
    8000,
    6300,
    5000,
    4000,
    3150,
    2500,
    2000,
    1600,
    1250,
    1000,
    800,
    630,
    500,
    400,
    315,
    250,
    200,
    160,
    125,
    100,
    80,
    63,
    50,
]

# Match face idMat in python_bindings/tests/mesh.cbin at pinned commit.
MATERIAL_IDS = (100, 101)

# Punctual receivers kept inside the official mesh bbox [0,20]x[0,30]x[0,10].
RECEIVERS = [
    # id, name, x, y, z, u, v, w
    (3431, "r_top", 2.0, 2.0, 3.0, 0.0, 0.0, -1.0),
    (3911, "r_right", 2.0, 1.0, 2.0, 0.0, 1.0, 0.0),
    (3751, "r_left", 2.0, 3.0, 2.0, 0.0, -1.0, 0.0),
    (3112, "r_front", 3.0, 2.0, 2.0, -1.0, 0.0, 0.0),
    (3591, "r_bot", 2.0, 2.0, 1.0, 0.0, 0.0, 1.0),
    (3271, "r_back", 1.0, 2.0, 2.0, 1.0, 0.0, 0.0),
]


def _f(value: float, digits: int = 6) -> str:
    return f"{value:.{digits}f}"


def _bfreq_absorb(absorb: float) -> list[ET.Element]:
    nodes: list[ET.Element] = []
    for freq in FREQS:
        el = ET.Element("bfreq")
        el.set("freq", str(freq))
        el.set("absorb", _f(absorb))
        el.set("diffusion", _f(0.0))
        el.set("loi", "0")
        nodes.append(el)
    return nodes


def _bfreq_source_db(base_db: float = 80.0) -> list[ET.Element]:
    """Lw spectrum placeholder structure from upstream test (not published as Lp)."""
    nodes: list[ET.Element] = []
    # Mirror upstream shape: higher bands slightly louder around base.
    # Values are source Lw in config, not result Lp maps.
    offset = {
        20000: 13.140419,
        16000: 12.140419,
        12500: 11.140419,
        10000: 10.140419,
        8000: 9.140419,
        6300: 8.140419,
        5000: 7.140419,
        4000: 6.140419,
        3150: 5.140419,
        2500: 4.140419,
        2000: 3.140419,
        1600: 2.140419,
        1250: 1.140419,
        1000: 0.140419,
        800: -0.859581,
        630: -1.859581,
        500: -2.859581,
        400: -3.859581,
        315: -4.859581,
        250: -5.859581,
        200: -6.859581,
        160: -7.859581,
        125: -8.859581,
        100: -9.859581,
        80: -10.859581,
        63: -11.859581,
        50: -12.859581,
    }
    for freq in FREQS:
        el = ET.Element("bfreq")
        el.set("freq", str(freq))
        el.set("db", _f(base_db + offset[freq]))
        nodes.append(el)
    return nodes


def build_config(*, nb_particles: int, seed: int) -> ET.ElementTree:
    root = ET.Element("configuration")
    # Must end with path separator: SPPS does workingDir+modelName (".mesh.cbin" if ".").
    root.set("workingdirectory", "./")

    sim = ET.SubElement(root, "simulation")
    sim.set("recepteurss_directory", "recepteurss")
    sim.set("recepteurss_filename", "Sound_level.csbin")
    sim.set("recepteurss_cut_filename", "rs_cut.csbin")
    sim.set("receiversp_directory", "Punctual receivers")
    sim.set("receiversp_filename", "Sound level.recp")
    sim.set("receiversp_filename_adv", "Advanced sound level.gap")
    sim.set("cumul_filename", "Total energy.recp")
    sim.set("modelName", "mesh.cbin")
    sim.set("tetrameshFileName", "tetramesh.mbin")
    sim.set("abs_atmo_calc", "1")
    sim.set("enc_calc", "0")
    sim.set("trans_calc", "0")
    sim.set("direct_calc", "0")
    sim.set("duree_simulation", _f(0.1))
    sim.set("output_recp_bysource", "0")
    sim.set("output_recs_byfreq", "0")
    sim.set("surf_receiv_method", "0")
    sim.set("random_seed", str(seed))
    sim.set("computation_method", "1")
    sim.set("nbparticules", str(nb_particles))
    sim.set("nbparticules_rendu", "0")
    sim.set("pasdetemps", _f(0.0005))
    sim.set("rayon_recepteurp", _f(0.31))
    sim.set("trans_epsilon", _f(5.0))
    sim.set("intensity_filename", "Intensity vector.rpi")
    sim.set("intensity_folder", "IntensityAnimation")
    sim.set("intensity_rp_filename", "ponct_intensity.gabe")
    sim.set("stats_filename", "statsSPPS.gabe")
    sim.set("particules_directory", "particles")
    sim.set("particules_filename", "particles.pbin")
    sim.set("directivities_directory", "")

    freq_enum = ET.SubElement(sim, "freq_enum")
    # Only a few bands: keep smoke run short while exercising multi-band path.
    calc_bands = {100, 1000}
    for freq in FREQS:
        bf = ET.SubElement(freq_enum, "bfreq")
        bf.set("freq", str(freq))
        bf.set("docalc", "1" if freq in calc_bands else "0")

    atm = ET.SubElement(root, "condition_atmospherique")
    atm.set("absatmo", _f(0.0))
    atm.set("disable_absatmo_computation", "0")
    atm.set("humidite", _f(50.0))
    atm.set("pression", _f(101325.0))
    atm.set("alog", _f(0.0))
    atm.set("blin", _f(0.0))
    atm.set("lst_soltype", "1")
    atm.set("z0", _f(0.02))
    atm.set("temperature", _f(20.0))

    mats = ET.SubElement(root, "surface_absorption_enum")
    # 100: moderate absorption; 101: higher — both present on official mesh faces.
    for mat_id, absorb in ((100, 0.20), (101, 0.40)):
        ts = ET.SubElement(mats, "type_surface")
        ts.set("id", str(mat_id))
        ts.set("resistivite", _f(100.0))
        ts.set("side_material", "1")
        for child in _bfreq_absorb(absorb):
            ts.append(child)

    ET.SubElement(root, "subdomains")

    sources = ET.SubElement(root, "sources")
    src = ET.SubElement(sources, "source")
    src.set("id", "4423")
    src.set("name", "main_src")
    src.set("directivity_file", "speaker-test3.txt")
    src.set("x", _f(2.0))
    src.set("y", _f(2.0))
    src.set("z", _f(2.0))
    src.set("delay", _f(0.0))
    src.set("u", _f(1.0))
    src.set("v", _f(0.0))
    src.set("w", _f(0.0))
    src.set("directivite", "5")
    for child in _bfreq_source_db():
        src.append(child)

    recs = ET.SubElement(root, "recepteursp")
    # Background noise spectrum on receivers (upstream shape; not a published Lp map).
    noise_db = {
        20000: -6.859580,
        16000: -7.859580,
        12500: -8.859579,
        10000: -9.859579,
        8000: -10.859579,
        6300: -11.859579,
        5000: -12.859579,
        4000: -13.859579,
        3150: -14.859579,
        2500: -15.859579,
        2000: -16.859579,
        1600: -17.859579,
        1250: -18.859579,
        1000: -19.859579,
        800: -20.859579,
        630: -21.859579,
        500: -22.859579,
        400: -23.859579,
        315: -24.859579,
        250: -25.859579,
        200: -26.859579,
        160: -27.859579,
        125: -28.859579,
        100: -29.859579,
        80: -30.859579,
        63: -31.859579,
        50: -32.859581,
    }
    for rid, name, x, y, z, u, v, w in RECEIVERS:
        rp = ET.SubElement(recs, "recepteur_ponctuel")
        rp.set("id", str(rid))
        rp.set("name", name)
        rp.set("lbl", name)
        rp.set("x", _f(x))
        rp.set("y", _f(y))
        rp.set("z", _f(z))
        rp.set("u", _f(u))
        rp.set("v", _f(v))
        rp.set("w", _f(w))
        for freq in FREQS:
            bf = ET.SubElement(rp, "bfreq")
            bf.set("freq", str(freq))
            bf.set("db", _f(noise_db[freq]))

    # Official mesh has no surface-receiver face markers (idRs=-1).
    ET.SubElement(root, "recepteurss")
    ET.SubElement(root, "encombrement_enum")

    tree = ET.ElementTree(root)
    return tree


def _indent(elem: ET.Element, level: int = 0) -> None:
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            _indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        last = elem[-1]
        if not last.tail or not last.tail.strip():
            last.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output config.xml path",
    )
    parser.add_argument("--nb-particles", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    tree = build_config(nb_particles=args.nb_particles, seed=args.seed)
    _indent(tree.getroot())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # XML declaration + UTF-8 (ENG-007).
    tree.write(
        args.out,
        encoding="utf-8",
        xml_declaration=True,
        short_empty_elements=True,
    )
    # Ensure LF and no BOM surprises on Windows writers.
    text = args.out.read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n")
    # Defensive: no commas in numeric attributes.
    if re.search(r'="[^"]*,[^"]*"', text):
        print("ERROR: comma decimal separator leaked into config", file=sys.stderr)
        return 1
    args.out.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
