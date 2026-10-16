#!/usr/bin/env python3
"""Apply SonoPlan SPPS source patches to a checked-out I-Simpa tree.

Do NOT undefine UTILISER_MAILLAGE_OPTIMISATION: the upstream #ifndef path does
not compile against the current core types (doInvertNormal / percCollision).

Root cause of CI energySumGlobal=0 (verified on official control + minimal_room):

1. Under UTILISER, FreeParticleTranslation only calls ParticuleFreeTranslation
   when ``currentTetra->linkedRecepteurP`` is set — end-tetra deposits miss when
   linking is incomplete on the 6-tetra smoke cube.
2. ParticuleFreeTranslation only walked that link list (not all receivers).
3. ``cdt_vol`` is only set when ``indexTetra`` is valid in Expand; on miss,
   save writes ``energy_sum * cdt_vol`` → zeros on disk even if energy accumulated.
4. Unused ``static const`` markers are stripped by -O2 / gc-sections.

This script (string transforms only — do NOT git-apply documenting ``*.patch``):

1. Always set ``cdt_vol = (c·ρ)/V_sphere`` for every punctual receiver.
2. Link every tetra within rayon+10 (belt-and-suspenders).
3. Deposit against the full ``recepteur_p_List``.
4. Always call ParticuleFreeTranslation under UTILISER (drop link gate).
5. Embed a ``__attribute__((used))`` marker touched from the UTILISER path;
   ``build-spps-native.sh`` fails if the marker is absent in the binary.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
PATCH_DIR = ENGINE_DIR / "patches"
MARKER = "sonoplan-deposit-all-recp-v3"

_CHECK_SOURCE = (
    "bool CheckSourcePosition(std::vector<t_Source *> &lstSource, t_Mesh *model) {"
)

_SONOPLAN_EXPAND_TAIL = """
	// SonoPlan: always set cdt_vol (Init may leave it unset if indexTetra miss).
	const float cdtVolAll=(float)(((*configManager.FastGetConfigValue(Base_Core_Configuration::FPROP_CELERITE))*(*configManager.FastGetConfigValue(Base_Core_Configuration::FPROP_RHO)))/volumeRP);
	for(std::size_t idrecp=0;idrecp<lstRecepteurP->size();idrecp++)
		lstRecepteurP->at(idrecp)->cdt_vol=cdtVolAll;
	// SonoPlan: link every tetra that can intersect the receiver sphere.
	for(std::size_t idrecp=0;idrecp<lstRecepteurP->size();idrecp++)
	{
		t_Recepteur_P* rp=lstRecepteurP->at(idrecp);
		for(uentier idtetra=0;idtetra<tetraMesh->tetraedresSize;idtetra++)
		{
			t_Tetra* tet=&tetraMesh->tetraedres[idtetra];
			decimal dCenter=rp->position.distance(tet->g);
			if(dCenter<=rayonRecepteurP+10.f)
			{
				if(!tet->linkedRecepteurP)
					tet->makeTabRecp();
				if(!ContainsRP(rp,tet->linkedRecepteurP))
					tet->linkedRecepteurP->push_back(rp);
			}
		}
	}
	std::cerr<<"SonoPlan ExpandPunctual: n_recp="<<lstRecepteurP->size()
		<<" rayon="<<rayonRecepteurP<<" cdt_vol="<<cdtVolAll
		<<" n_tetra="<<tetraMesh->tetraedresSize<<std::endl;
}
"""

_OLD_DEPOSIT_ASCII = """	if(particleInfos.currentTetra->linkedRecepteurP)
	{

		for(std::size_t idrecp=0;idrecp<particleInfos.currentTetra->linkedRecepteurP->size();idrecp++)
		{
			t_Recepteur_P* currentRecp=particleInfos.currentTetra->linkedRecepteurP->at(idrecp);"""

_NEW_DEPOSIT = """	// SonoPlan: deposit against ALL punctual receivers (tetra link is optional).
	{
		std::vector<t_Recepteur_P*>* recpList=&paramReport.configManager->recepteur_p_List;
		for(std::size_t idrecp=0;idrecp<recpList->size();idrecp++)
		{
			t_Recepteur_P* currentRecp=recpList->at(idrecp);"""

# UTILISER FreeParticleTranslation: drop end-tetra link gate (compiled path).
_OLD_UTILISER_CALL = (
    "\tif(configurationP.currentTetra->linkedRecepteurP)\n"
    "\t\treportTool->ParticuleFreeTranslation("
    "configurationP,configurationP.position+translationVector);"
)

_NEW_UTILISER_CALL = (
    "\t// SonoPlan: always deposit under UTILISER (link gate skipped energy on smoke meshes).\n"
    "\tsonoplan_spps_touch_marker();\n"
    "\tif(configurationP.currentTetra)\n"
    "\t\treportTool->ParticuleFreeTranslation("
    "configurationP,configurationP.position+translationVector);"
)


def _link_and_cdt(src: Path) -> None:
    target = src / "src" / "spps" / "sppsInitialisation.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
    if "SonoPlan ExpandPunctual: n_recp=" in text:
        print(f"expand-cdt-link: already applied in {target}")
        return

    anchor = (
        "RecursiveTetraTest(lstRecepteurP->at(idrecp), rayonRecepteurP, "
        "recpTetra->voisins[idVoisin], tetraMesh);"
    )
    a = text.find(anchor)
    b = text.find(_CHECK_SOURCE)
    if a < 0 or b < 0 or b <= a:
        raise SystemExit(
            f"expand-cdt-link: ExpandPunctual/CheckSourcePosition anchors missing in {target}"
        )

    mid = text[a:b]
    upstream_close = "\n\t\t\t}\n\t\t}\n\t}"
    c = mid.find(upstream_close)
    if c < 0:
        raise SystemExit(f"expand-cdt-link: upstream Expand close not found in {target}")
    keep = mid[: c + len(upstream_close)]
    new_mid = keep + "\n" + _SONOPLAN_EXPAND_TAIL + "\n"
    text = text[:a] + new_mid + text[b:]
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"expand-cdt-link: applied in {target}")


def _deposit_all_receivers(src: Path) -> None:
    target = src / "src" / "spps" / "input_output" / "reportmanager.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
    if "SonoPlan: deposit against ALL punctual receivers" in text:
        print(f"deposit-all-recp: already applied in {target}")
        return
    if _OLD_DEPOSIT_ASCII not in text:
        raise SystemExit(
            f"deposit-all-recp: ParticuleFreeTranslation gate not found in {target}"
        )
    target.write_text(
        text.replace(_OLD_DEPOSIT_ASCII, _NEW_DEPOSIT, 1), encoding="utf-8", newline="\n"
    )
    print(f"deposit-all-recp: applied in {target}")


def _ungate_utiliser_deposit(src: Path) -> None:
    """Always call ParticuleFreeTranslation on the UTILISER (compiled) path."""
    target = src / "src" / "spps" / "CalculationCore.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
    if "SonoPlan: always deposit under UTILISER" in text:
        print(f"utiliser-ungate: already applied in {target}")
        return
    if _OLD_UTILISER_CALL not in text:
        raise SystemExit(
            f"utiliser-ungate: linkedRecepteurP call gate not found in {target}"
        )
    text = text.replace(_OLD_UTILISER_CALL, _NEW_UTILISER_CALL, 1)
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"utiliser-ungate: applied in {target}")


def _embed_marker(src: Path) -> None:
    target = src / "src" / "spps" / "CalculationCore.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
    # Drop any prior marker symbols (old .patch or previous apply).
    text = re.sub(
        r"(?:__attribute__\(\(used\)\)\s*)?static const char sonoplan_spps_patch\[\] = \"[^\"]*\";\n?",
        "",
        text,
    )
    text = re.sub(
        r"static void sonoplan_spps_touch_marker\(void\)\s*\{[^}]*\}\n?",
        "",
        text,
    )
    # Keep SonoPlan ungating comment/call; only strip orphaned touch lines that
    # are not part of our ungating block (idempotent re-apply).
    text = re.sub(
        r"(?<!UTILISER \(link gate skipped energy on smoke meshes\)\.\n)"
        r"\tsonoplan_spps_touch_marker\(\);\n",
        "",
        text,
    )
    # Simpler: remove ALL touch calls then re-insert via ungating (already done).
    text = text.replace("\tsonoplan_spps_touch_marker();\n", "")

    needle = '#include "CalculationCore.h"'
    if needle not in text:
        raise SystemExit(f"patch-marker: include missing in {target}")
    blob = (
        needle
        + "\n"
        + f'__attribute__((used)) static const char sonoplan_spps_patch[] = "{MARKER}";\n'
        + "static void sonoplan_spps_touch_marker(void) "
        + "{ volatile const char* p = sonoplan_spps_patch; (void)p[0]; }\n"
    )
    text = text.replace(needle, blob, 1)

    # Re-apply UTILISER ungating with touch (was stripped above if present).
    if "SonoPlan: always deposit under UTILISER" not in text:
        if _OLD_UTILISER_CALL not in text:
            raise SystemExit(
                "patch-marker: UTILISER deposit gate missing after marker scrub"
            )
        text = text.replace(_OLD_UTILISER_CALL, _NEW_UTILISER_CALL, 1)
    elif "sonoplan_spps_touch_marker();" not in text:
        text = text.replace(
            "\t// SonoPlan: always deposit under UTILISER "
            "(link gate skipped energy on smoke meshes).\n"
            "\tif(configurationP.currentTetra)\n",
            "\t// SonoPlan: always deposit under UTILISER "
            "(link gate skipped energy on smoke meshes).\n"
            "\tsonoplan_spps_touch_marker();\n"
            "\tif(configurationP.currentTetra)\n",
            1,
        )

    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"patch-marker: embedded {MARKER} in {target}")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print(f"usage: {Path(__file__).name} <isimpa-src-dir>", file=sys.stderr)
        return 2
    src = Path(args[0]).resolve()
    if not (src / "src" / "spps" / "CalculationCore.cpp").is_file():
        print(f"ERROR: not an I-Simpa tree: {src}", file=sys.stderr)
        return 1

    # Documenting engine/patches/*.patch are NOT applied: outdated markers clash
    # with string fallbacks (redefinition of sonoplan_spps_patch).
    for patch in sorted(PATCH_DIR.glob("*.patch")):
        print(f"skip git apply {patch.name} (string fallbacks are authoritative)")

    _link_and_cdt(src)
    _deposit_all_receivers(src)
    _ungate_utiliser_deposit(src)
    _embed_marker(src)

    init = (src / "src" / "spps" / "sppsInitialisation.cpp").read_text(encoding="utf-8")
    core = (src / "src" / "spps" / "CalculationCore.cpp").read_text(encoding="utf-8")
    report = (
        src / "src" / "spps" / "input_output" / "reportmanager.cpp"
    ).read_text(encoding="utf-8")
    if "SonoPlan ExpandPunctual: n_recp=" not in init:
        raise SystemExit("ERROR: expand-cdt-link missing after apply")
    if MARKER not in core:
        raise SystemExit("ERROR: patch marker missing after apply")
    if "SonoPlan: deposit against ALL punctual receivers" not in report:
        raise SystemExit("ERROR: deposit-all-recp missing after apply")
    if "SonoPlan: always deposit under UTILISER" not in core:
        raise SystemExit("ERROR: utiliser-ungate missing after apply")
    if "sonoplan_spps_touch_marker();" not in core:
        raise SystemExit("ERROR: marker touch missing from UTILISER path")
    types = (src / "src" / "spps" / "sppsTypes.h").read_text(encoding="utf-8")
    if "#define UTILISER_MAILLAGE_OPTIMISATION" not in types:
        raise SystemExit(
            "ERROR: UTILISER must stay defined (ifndef path does not compile)"
        )
    print(
        f"SPPS patches OK (marker={MARKER}, UTILISER kept, "
        "deposit-all+cdt_vol+utiliser-ungate)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
