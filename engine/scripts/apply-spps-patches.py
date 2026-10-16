#!/usr/bin/env python3
"""Apply SonoPlan SPPS source patches to a checked-out I-Simpa tree.

Do NOT undefine UTILISER_MAILLAGE_OPTIMISATION: the upstream #ifndef path does
not compile against the current core types (doInvertNormal / percCollision).

CI zero-energy: punctual deposit gated on tetra links; cdt_vol only set when
indexTetra is valid; unused static markers stripped by -O2. This script:

1. Links every tetra within rayon+10 (smoke 6-tetra cube).
2. Always sets cdt_vol = (c·ρ)/V_sphere for every punctual receiver.
3. Deposits against the full recepteur_p_List.
4. Embeds a used .rodata marker; build-spps-native.sh fails if absent in binary.
"""

from __future__ import annotations

import subprocess
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


def _link_and_cdt(src: Path) -> None:
    target = src / "src" / "spps" / "sppsInitialisation.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
    if "SonoPlan ExpandPunctual: n_recp=" in text:
        print(f"expand-cdt-link: already applied in {target}")
        return

    # Cut from first RecursiveTetraTest call through CheckSourcePosition.
    # Works on clean upstream and after partial 0002 link-only patch.
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

    # Keep upstream RecursiveTetraTest + the three closing braces of the
    # idVoisin / if(indexTetra) / for(idrecp) loops (not the function `}`).
    mid = text[a:b]
    # After RecursiveTetraTest block: "\n\t\t\t}\n\t\t}\n\t}\n" then optional
    # SonoPlan link block then "}\n\n".
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


def _embed_marker(src: Path) -> None:
    target = src / "src" / "spps" / "CalculationCore.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
    if MARKER in text:
        print(f"patch-marker: already present in {target}")
        return
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
    util_ft = (
        "void CalculationCore::FreeParticleTranslation"
        "(CONF_PARTICULE &configurationP,const vec3 &translationVector)\n"
        "{\n"
        "\treportTool->ParticuleFreeTranslation"
    )
    util_ft_new = (
        "void CalculationCore::FreeParticleTranslation"
        "(CONF_PARTICULE &configurationP,const vec3 &translationVector)\n"
        "{\n"
        "\tsonoplan_spps_touch_marker();\n"
        "\treportTool->ParticuleFreeTranslation"
    )
    idx = text.rfind(util_ft)
    if idx < 0:
        raise SystemExit("patch-marker: UTILISER FreeParticleTranslation not found")
    text = text[:idx] + util_ft_new + text[idx + len(util_ft) :]
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

    # Documenting .patch files may fail; string fallbacks below are authoritative.
    for patch in sorted(PATCH_DIR.glob("*.patch")):
        print(f"git apply {patch.name} ...")
        r = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", str(patch)],
            cwd=src,
            check=False,
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            print(f"  ok: {patch.name}")
        else:
            print(f"  git apply failed ({r.returncode}); string fallbacks follow")
            if r.stderr:
                print(r.stderr[:400])

    _link_and_cdt(src)
    _deposit_all_receivers(src)
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
    types = (src / "src" / "spps" / "sppsTypes.h").read_text(encoding="utf-8")
    if "#define UTILISER_MAILLAGE_OPTIMISATION" not in types:
        raise SystemExit(
            "ERROR: UTILISER must stay defined (ifndef path does not compile)"
        )
    print(f"SPPS patches OK (marker={MARKER}, UTILISER kept, deposit-all+cdt_vol)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
