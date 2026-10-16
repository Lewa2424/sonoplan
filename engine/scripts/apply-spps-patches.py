#!/usr/bin/env python3
"""Apply SonoPlan SPPS source patches to a checked-out I-Simpa tree.

Do NOT undefine UTILISER_MAILLAGE_OPTIMISATION: the upstream #ifndef path does
not compile against the current core types (doInvertNormal / percCollision).

Facts from CI (Total energy.recp > 0, punctual .recp == 0, ExpandPunctual
cdt_vol=3311.6, marker present):

* Upstream UTILISER FreeParticleTranslation already always calls
  ParticuleFreeTranslation (no linkedRecepteurP gate). A prior "ungate" that
  rewrote the #ifndef overload was a false fix (dead code under UTILISER).
* Deposit-all + force cdt_vol alone still left energySumGlobal=0 — RaySphere
  can clamp to Lintersect==0 while the particle is inside the sphere.

This script (string transforms only — do NOT git-apply documenting ``*.patch``):

1. Always set ``cdt_vol = (c·ρ)/V_sphere`` for every punctual receiver.
2. Link every tetra within rayon+10.
3. Deposit against the full ``recepteur_p_List``.
4. If RaySphere chord clamps to 0 but an endpoint is inside the sphere, keep
   presence length = step length (no invented dB — still real particle energy).
5. Embed a ``__attribute__((used))`` marker touched from the UTILISER path.
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

_OLD_UTILISER_FPT = (
    "void CalculationCore::FreeParticleTranslation"
    "(CONF_PARTICULE &configurationP,const vec3 &translationVector)\n"
    "{\n"
    "\treportTool->ParticuleFreeTranslation"
    "(configurationP,configurationP.position+translationVector);"
)

_NEW_UTILISER_FPT = (
    "void CalculationCore::FreeParticleTranslation"
    "(CONF_PARTICULE &configurationP,const vec3 &translationVector)\n"
    "{\n"
    "\tsonoplan_spps_touch_marker();\n"
    "\treportTool->ParticuleFreeTranslation"
    "(configurationP,configurationP.position+translationVector);"
)

_OLD_DEPOSIT_BODY = """\t\t\t\t\tfloat norm_dir=(direction).length();
\t\t\t\t\tl_decimal Lintersect=abs(mu2-mu1)*norm_dir;
\t\t\t\t\tif(Lintersect>0)
\t\t\t\t\t{
\t\t\t\t\t\tl_decimal cosphi=cos(M_PIDIV2-direction.angle(currentRecp->orientation));
\t\t\t\t\t\tconst l_decimal energy=particleInfos.energie*Lintersect;"""

_NEW_DEPOSIT_BODY = """\t\t\t\t\tfloat norm_dir=(direction).length();
\t\t\t\t\tl_decimal Lintersect=abs(mu2-mu1)*norm_dir;
\t\t\t\t\t// SonoPlan: if RaySphere clamp wiped the chord but an endpoint is
\t\t\t\t\t// inside the sphere, keep presence length = step length.
\t\t\t\t\tif(Lintersect<=0 && norm_dir>0)
\t\t\t\t\t{
\t\t\t\t\t\tconst float rRp=*paramReport.configManager->FastGetConfigValue(Core_Configuration::FPROP_RAYON_RECEPTEURP);
\t\t\t\t\t\tconst float d0=(float)particleInfos.position.distance(currentRecp->position);
\t\t\t\t\t\tconst float d1=(float)nextPosition.distance(currentRecp->position);
\t\t\t\t\t\tif(d0<rRp || d1<rRp)
\t\t\t\t\t\t\tLintersect=norm_dir;
\t\t\t\t\t}
\t\t\t\t\tif(Lintersect>0)
\t\t\t\t\t{
\t\t\t\t\t\tl_decimal cosphi=cos(M_PIDIV2-direction.angle(currentRecp->orientation));
\t\t\t\t\t\tconst l_decimal energy=particleInfos.energie*Lintersect;"""


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


def _robust_chord_deposit(src: Path) -> None:
    target = src / "src" / "spps" / "input_output" / "reportmanager.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
    if "SonoPlan: if RaySphere clamp wiped the chord" in text:
        print(f"robust-chord: already applied in {target}")
        return
    if _OLD_DEPOSIT_BODY not in text:
        raise SystemExit(f"robust-chord: deposit Lintersect block not found in {target}")
    target.write_text(
        text.replace(_OLD_DEPOSIT_BODY, _NEW_DEPOSIT_BODY, 1), encoding="utf-8", newline="\n"
    )
    print(f"robust-chord: applied in {target}")


def _touch_utiliser_fpt(src: Path) -> None:
    target = src / "src" / "spps" / "CalculationCore.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
    if "sonoplan_spps_touch_marker();\n\treportTool->ParticuleFreeTranslation" in text:
        print(f"utiliser-touch: already applied in {target}")
        return
    idx = text.rfind(_OLD_UTILISER_FPT)
    if idx < 0:
        raise SystemExit(
            f"utiliser-touch: UTILISER FreeParticleTranslation not found in {target}"
        )
    text = text[:idx] + _NEW_UTILISER_FPT + text[idx + len(_OLD_UTILISER_FPT) :]
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"utiliser-touch: applied in {target}")


def _embed_marker(src: Path) -> None:
    target = src / "src" / "spps" / "CalculationCore.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
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
    text = text.replace("\tsonoplan_spps_touch_marker();\n", "")
    # Undo prior false-fix that rewrote the #ifndef overload.
    text = text.replace(
        "\t// SonoPlan: always deposit under UTILISER "
        "(link gate skipped energy on smoke meshes).\n",
        "",
    )
    ifndef_broken = (
        "\tif(configurationP.currentTetra)\n"
        "\t\treportTool->ParticuleFreeTranslation("
        "configurationP,configurationP.position+translationVector);"
    )
    ifndef_ok = (
        "\tif(configurationP.currentTetra->linkedRecepteurP)\n"
        "\t\treportTool->ParticuleFreeTranslation("
        "configurationP,configurationP.position+translationVector);"
    )
    if ifndef_broken in text and ifndef_ok not in text:
        text = text.replace(ifndef_broken, ifndef_ok, 1)

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
    target.write_text(text, encoding="utf-8", newline="\n")
    _touch_utiliser_fpt(src)
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

    for patch in sorted(PATCH_DIR.glob("*.patch")):
        print(f"skip git apply {patch.name} (string fallbacks are authoritative)")

    _link_and_cdt(src)
    _deposit_all_receivers(src)
    _robust_chord_deposit(src)
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
    if "SonoPlan: if RaySphere clamp wiped the chord" not in report:
        raise SystemExit("ERROR: robust-chord missing after apply")
    if "sonoplan_spps_touch_marker();\n\treportTool->ParticuleFreeTranslation" not in core:
        raise SystemExit("ERROR: UTILISER touch+FPT call missing after apply")
    if "SonoPlan: always deposit under UTILISER" in core:
        raise SystemExit("ERROR: false #ifndef ungate comment still present")
    types = (src / "src" / "spps" / "sppsTypes.h").read_text(encoding="utf-8")
    if "#define UTILISER_MAILLAGE_OPTIMISATION" not in types:
        raise SystemExit(
            "ERROR: UTILISER must stay defined (ifndef path does not compile)"
        )
    print(
        f"SPPS patches OK (marker={MARKER}, UTILISER kept, "
        "deposit-all+cdt_vol+robust-chord)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
