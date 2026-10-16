#!/usr/bin/env python3
"""Apply SonoPlan SPPS source patches to a checked-out I-Simpa tree.

Do NOT undefine UTILISER_MAILLAGE_OPTIMISATION: the upstream #ifndef path does
not compile against current core types.

I-Simpa polarity (easy to get backwards):

* ``#define UTILISER_MAILLAGE_OPTIMISATION`` is set in sppsTypes.h.
* Compiled FreeParticleTranslation is under ``#else`` (after
  ``#ifndef UTILISER_…``) and **already always** calls ParticuleFreeTranslation.
* The ``linkedRecepteurP`` gate lives only in the dead ``#ifndef`` overload.

Root cause of CI punctual energySumGlobal=0 (Total energy.recp CAN be >0):

1. ParticuleFreeTranslation only walked ``linkedRecepteurP`` (not all receivers).
2. ``cdt_vol`` may stay 0 if indexTetra miss → save writes energy*0.
3. RaySphere can return false OR clamp chord to 0 while the particle is inside
   the sphere (common when source/receiver are colocated / short steps).
4. Unused ``static const`` markers are stripped by -O2.

This script (string transforms only — never git-apply documenting ``*.patch``):

1. Force ``cdt_vol = (c·ρ)/V_sphere`` + link tetras within rayon+10.
2. Deposit against full ``recepteur_p_List``.
3. If RaySphere misses/clamps but an endpoint is inside, use step length
   (real particle energy, not invented dB).
4. Touch used marker from the **compiled** UTILISER (``#else``) FreeParticleTranslation.
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

# Compiled UTILISER FreeParticleTranslation is the #else overload — already ungated.
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
    "\t// SonoPlan: touch marker on compiled UTILISER (#else) path.\n"
    "\tsonoplan_spps_touch_marker();\n"
    "\treportTool->ParticuleFreeTranslation"
    "(configurationP,configurationP.position+translationVector);"
)

_OLD_RAYSPHERE_BLOCK = """\t\t\t\tif(RaySphere(particleInfos.position,nextPosition,currentRecp->position,*paramReport.configManager->FastGetConfigValue(Core_Configuration::FPROP_RAYON_RECEPTEURP),&mu1,&mu2))
\t\t\t\t{
\t\t\t\t\tif(mu2<0)
\t\t\t\t\t\tmu2=0;
\t\t\t\t\telse if(mu2>1)
\t\t\t\t\t\tmu2=1;
\t\t\t\t\tif(mu1<0)
\t\t\t\t\t\tmu1=0;
\t\t\t\t\telse if(mu1>1)
\t\t\t\t\t\tmu1=1;
\t\t\t\t\tfloat norm_dir=(direction).length();
\t\t\t\t\tl_decimal Lintersect=abs(mu2-mu1)*norm_dir;
\t\t\t\t\tif(Lintersect>0)
\t\t\t\t\t{
\t\t\t\t\t\tl_decimal cosphi=cos(M_PIDIV2-direction.angle(currentRecp->orientation));
\t\t\t\t\t\tconst l_decimal energy=particleInfos.energie*Lintersect;"""

_NEW_RAYSPHERE_BLOCK = """\t\t\t\tfloat norm_dir=(direction).length();
\t\t\t\tl_decimal Lintersect=0;
\t\t\t\tif(RaySphere(particleInfos.position,nextPosition,currentRecp->position,*paramReport.configManager->FastGetConfigValue(Core_Configuration::FPROP_RAYON_RECEPTEURP),&mu1,&mu2))
\t\t\t\t{
\t\t\t\t\tif(mu2<0)
\t\t\t\t\t\tmu2=0;
\t\t\t\t\telse if(mu2>1)
\t\t\t\t\t\tmu2=1;
\t\t\t\t\tif(mu1<0)
\t\t\t\t\t\tmu1=0;
\t\t\t\t\telse if(mu1>1)
\t\t\t\t\t\tmu1=1;
\t\t\t\t\tLintersect=abs(mu2-mu1)*norm_dir;
\t\t\t\t}
\t\t\t\t// SonoPlan: RaySphere may miss (a≈0 / float) while the particle is
\t\t\t\t// inside the sphere — keep presence length from the step.
\t\t\t\tif(Lintersect<=0 && norm_dir>0)
\t\t\t\t{
\t\t\t\t\tconst float rRp=*paramReport.configManager->FastGetConfigValue(Core_Configuration::FPROP_RAYON_RECEPTEURP);
\t\t\t\t\tconst float d0=(float)particleInfos.position.distance(currentRecp->position);
\t\t\t\t\tconst float d1=(float)nextPosition.distance(currentRecp->position);
\t\t\t\t\tif(d0<rRp || d1<rRp)
\t\t\t\t\t\tLintersect=norm_dir;
\t\t\t\t}
\t\t\t\tif(Lintersect>0)
\t\t\t\t{
\t\t\t\t\tl_decimal cosphi=cos(M_PIDIV2-direction.angle(currentRecp->orientation));
\t\t\t\t\tconst l_decimal energy=particleInfos.energie*Lintersect;"""


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


def _robust_outside_raysphere(src: Path) -> None:
    target = src / "src" / "spps" / "input_output" / "reportmanager.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
    if "SonoPlan: RaySphere may miss" in text:
        print(f"robust-outside-rs: already applied in {target}")
        return
    if "SonoPlan: if RaySphere clamp wiped the chord" in text:
        old_inside = """\t\t\t\t\tfloat norm_dir=(direction).length();
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
        upstream_inside = """\t\t\t\t\tfloat norm_dir=(direction).length();
\t\t\t\t\tl_decimal Lintersect=abs(mu2-mu1)*norm_dir;
\t\t\t\t\tif(Lintersect>0)
\t\t\t\t\t{
\t\t\t\t\t\tl_decimal cosphi=cos(M_PIDIV2-direction.angle(currentRecp->orientation));
\t\t\t\t\t\tconst l_decimal energy=particleInfos.energie*Lintersect;"""
        if old_inside not in text:
            raise SystemExit(
                "robust-outside-rs: old inside-RaySphere robust-chord present but "
                "shape unknown; reset I-Simpa tree and re-apply"
            )
        text = text.replace(old_inside, upstream_inside, 1)
        target.write_text(text, encoding="utf-8", newline="\n")
        text = target.read_text(encoding="utf-8", errors="replace")
        print(f"robust-outside-rs: stripped old inside-chord in {target}")

    if _OLD_RAYSPHERE_BLOCK not in text:
        raise SystemExit(f"robust-outside-rs: RaySphere deposit block not found in {target}")
    text = text.replace(_OLD_RAYSPHERE_BLOCK, _NEW_RAYSPHERE_BLOCK, 1)
    # OLD nested if(RaySphere){ if(Lintersect){ ... } } left an extra closer.
    orphan = (
        "                        }\n"
        "\t\t\t\t\t}\n"
        "\t\t\t\t}\n"
        "\t\t\t}\n"
    )
    fixed = (
        "                        }\n"
        "\t\t\t\t\t}\n"
        "\t\t\t}\n"
    )
    if orphan not in text:
        raise SystemExit(
            f"robust-outside-rs: expected orphan RaySphere closer not found in {target}"
        )
    text = text.replace(orphan, fixed, 1)
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"robust-outside-rs: applied in {target}")


def _touch_compiled_utiliser_fpt(src: Path) -> None:
    """Insert marker touch on the compiled #else UTILISER FreeParticleTranslation."""
    target = src / "src" / "spps" / "CalculationCore.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
    if "SonoPlan: touch marker on compiled UTILISER (#else) path." in text:
        print(f"utiliser-touch: already applied in {target}")
        return
    # Prefer the #else overload: it is the last FreeParticleTranslation that
    # starts with an immediate ParticuleFreeTranslation call.
    idx = text.rfind(_OLD_UTILISER_FPT)
    if idx < 0:
        raise SystemExit(
            f"utiliser-touch: compiled UTILISER FreeParticleTranslation not found in {target}"
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
    # Undo false ungates of the dead #ifndef overload from prior commits.
    for bad in (
        "\t// SonoPlan: always deposit under UTILISER (compiled path; "
        "do not confuse with #ifndef overload).\n",
        "\t// SonoPlan: always deposit under UTILISER "
        "(link gate skipped energy on smoke meshes).\n",
        "\t// SonoPlan: touch marker on compiled UTILISER (#else) path.\n",
    ):
        text = text.replace(bad, "")
    text = text.replace("\tsonoplan_spps_touch_marker();\n", "")
    # Restore #ifndef gate if a prior false ungate replaced it with currentTetra-only.
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
    _touch_compiled_utiliser_fpt(src)
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
    _robust_outside_raysphere(src)
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
    if "SonoPlan: RaySphere may miss" not in report:
        raise SystemExit("ERROR: robust-outside-rs missing after apply")
    if "SonoPlan: touch marker on compiled UTILISER (#else) path." not in core:
        raise SystemExit("ERROR: compiled UTILISER touch missing after apply")
    # Dead #ifndef path must KEEP its linkedRecepteurP gate (document polarity).
    ifndef_gate = (
        "\tif(configurationP.currentTetra->linkedRecepteurP)\n"
        "\t\treportTool->ParticuleFreeTranslation"
    )
    if ifndef_gate not in core:
        raise SystemExit("ERROR: #ifndef linkedRecepteurP gate was incorrectly removed")
    # Compiled #else body must still always call deposit (no linkedRecepteurP gate).
    else_idx = core.rfind("void CalculationCore::FreeParticleTranslation")
    else_body = core[else_idx : else_idx + 500]
    if "linkedRecepteurP" in else_body:
        raise SystemExit("ERROR: compiled UTILISER FPT unexpectedly gated")
    if "sonoplan_spps_touch_marker();" not in else_body:
        raise SystemExit("ERROR: touch not on compiled UTILISER FPT")
    types = (src / "src" / "spps" / "sppsTypes.h").read_text(encoding="utf-8")
    if "#define UTILISER_MAILLAGE_OPTIMISATION" not in types:
        raise SystemExit(
            "ERROR: UTILISER must stay defined (ifndef path does not compile)"
        )
    print(
        f"SPPS patches OK (marker={MARKER}, UTILISER kept, "
        "deposit-all+cdt_vol+robust-outside-rs+compiled-touch)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
