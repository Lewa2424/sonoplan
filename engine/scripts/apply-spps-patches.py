#!/usr/bin/env python3
"""Apply SonoPlan SPPS source patches to a checked-out I-Simpa tree.

1. Disable UTILISER_MAILLAGE_OPTIMISATION so FreeParticleTranslation uses the
   non-optimised path that always calls ParticuleFreeTranslation (deposit).
2. Rewrite the UTILISER FreeParticleTranslation body to deposit on the *start*
   tetra before navigation (safe if UTILISER is re-enabled later).
3. Expand punctual-receiver↔tetra links to every tetra near the receiver
   sphere (6-tetra cube left CI with wall hits but zero .recp energy).
4. Embed a .rodata marker so CI can prove the patched binary was shipped.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
PATCH_DIR = ENGINE_DIR / "patches"
MARKER = "sonoplan-deposit-start-tetra-v2"

_OLD_UTILISER = "#define UTILISER_MAILLAGE_OPTIMISATION\n"
_NEW_UTILISER = (
    f"/* SonoPlan {_MARKER}: disable UTILISER end-tetra-only punctual deposit */\n"
    "// #define UTILISER_MAILLAGE_OPTIMISATION\n"
)

# Exact fragment from I-Simpa 929a5c8e… src/spps/CalculationCore.cpp (UTILISER)
_OLD_FPT = """void CalculationCore::FreeParticleTranslation(CONF_PARTICULE &configurationP,const vec3 &translationVector)
{
	if(configurationP.currentTetra)
	{
		bool changeTetrahedra=true;
		float tMax=-1;
		while(changeTetrahedra) //On navigue de tetraedre a tetraedre jusqu'a ce que le point de collision soit plus loin que le vecteur de translation
		{
			changeTetrahedra=false;
			float t;
			entier_court idfacemaxdist=GetTetraFaceCollision(configurationP,translationVector,t);
			if(idfacemaxdist>=0 && t<1 && t>=-EPSILON)
			{
				if(configurationP.currentTetra->voisins[idfacemaxdist] && tMax<t) //
				{
					reportTool->ParticuleGoToNextTetrahedra(configurationP,configurationP.currentTetra->voisins[idfacemaxdist]);
					configurationP.currentTetra=configurationP.currentTetra->voisins[idfacemaxdist];
					changeTetrahedra=true;
					tMax=t;
				}
			}
		}
	}
	if(configurationP.currentTetra->linkedRecepteurP)
		reportTool->ParticuleFreeTranslation(configurationP,configurationP.position+translationVector);

	//////////////
	// Translation de la particule
	configurationP.position+=translationVector;
}"""

_NEW_FPT = """void CalculationCore::FreeParticleTranslation(CONF_PARTICULE &configurationP,const vec3 &translationVector)
{
	// SonoPlan: deposit on start-tetra linked receivers before navigating away.
	if(configurationP.currentTetra && configurationP.currentTetra->linkedRecepteurP)
		reportTool->ParticuleFreeTranslation(configurationP,configurationP.position+translationVector);

	if(configurationP.currentTetra)
	{
		bool changeTetrahedra=true;
		float tMax=-1;
		while(changeTetrahedra) //On navigue de tetraedre a tetraedre jusqu'a ce que le point de collision soit plus loin que le vecteur de translation
		{
			changeTetrahedra=false;
			float t;
			entier_court idfacemaxdist=GetTetraFaceCollision(configurationP,translationVector,t);
			if(idfacemaxdist>=0 && t<1 && t>=-EPSILON)
			{
				if(configurationP.currentTetra->voisins[idfacemaxdist] && tMax<t) //
				{
					reportTool->ParticuleGoToNextTetrahedra(configurationP,configurationP.currentTetra->voisins[idfacemaxdist]);
					configurationP.currentTetra=configurationP.currentTetra->voisins[idfacemaxdist];
					changeTetrahedra=true;
					tMax=t;
				}
			}
		}
	}

	//////////////
	// Translation de la particule
	configurationP.position+=translationVector;
}"""

_OLD_EXPAND_END = """			for(int idVoisin=0;idVoisin<4;idVoisin++)
			{
				RecursiveTetraTest(lstRecepteurP->at(idrecp), rayonRecepteurP, recpTetra->voisins[idVoisin], tetraMesh);
			}
		}
	}
}

bool CheckSourcePosition(std::vector<t_Source *> &lstSource, t_Mesh *model) {"""

_NEW_EXPAND_END = """			for(int idVoisin=0;idVoisin<4;idVoisin++)
			{
				RecursiveTetraTest(lstRecepteurP->at(idrecp), rayonRecepteurP, recpTetra->voisins[idVoisin], tetraMesh);
			}
		}
	}
	// SonoPlan: ensure every tetra that can intersect the receiver sphere is
	// linked. Upstream RecursiveTetraTest alone left CI minimal_room with
	// wall hits but zero punctual .recp energy on the 6-tetra cube.
	for(std::size_t idrecp=0;idrecp<lstRecepteurP->size();idrecp++)
	{
		t_Recepteur_P* rp=lstRecepteurP->at(idrecp);
		for(uentier idtetra=0;idtetra<tetraMesh->tetraedresSize;idtetra++)
		{
			t_Tetra* tet=&tetraMesh->tetraedres[idtetra];
			decimal dCenter=rp->position.distance(tet->g);
			// Conservative: tetra diameter of a 5 m cube cell << 10 m.
			if(dCenter<=rayonRecepteurP+10.f)
			{
				if(!tet->linkedRecepteurP)
					tet->makeTabRecp();
				if(!ContainsRP(rp,tet->linkedRecepteurP))
					tet->linkedRecepteurP->push_back(rp);
			}
		}
	}
}

bool CheckSourcePosition(std::vector<t_Source *> &lstSource, t_Mesh *model) {"""


def _disable_utiliser(src: Path) -> None:
    types = src / "src" / "spps" / "sppsTypes.h"
    text = types.read_text(encoding="utf-8", errors="replace")
    if MARKER in text:
        print(f"disable-UTILISER: already applied in {types}")
        return
    if _OLD_UTILISER not in text:
        raise SystemExit(f"disable-UTILISER: define not found in {types}")
    types.write_text(text.replace(_OLD_UTILISER, _NEW_UTILISER, 1), encoding="utf-8", newline="\n")
    print(f"disable-UTILISER: applied in {types}")


def _rewrite_fpt(src: Path) -> None:
    target = src / "src" / "spps" / "CalculationCore.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
    if _NEW_FPT in text:
        print(f"deposit-on-start-tetra: FreeParticleTranslation already rewritten")
    elif _OLD_FPT in text:
        text = text.replace(_OLD_FPT, _NEW_FPT, 1)
        print(f"deposit-on-start-tetra: rewritten FreeParticleTranslation in {target}")
    else:
        print(
            "deposit-on-start-tetra: UTILISER FreeParticleTranslation not found "
            "(ok when UTILISER is disabled — #else path deposits always)"
        )
    if MARKER not in text:
        needle = '#include "CalculationCore.h"'
        if needle not in text:
            raise SystemExit(f"marker embed: include missing in {target}")
        text = text.replace(
            needle,
            needle + f'\nstatic const char sonoplan_spps_patch[] = "{MARKER}";\n',
            1,
        )
        print(f"deposit-on-start-tetra: embedded {MARKER} in {target}")
    target.write_text(text, encoding="utf-8", newline="\n")


def _link_all_tetras(src: Path) -> None:
    target = src / "src" / "spps" / "sppsInitialisation.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
    if "SonoPlan: ensure every tetra that can intersect" in text:
        print(f"link-all-tetras-within-rayon: already applied in {target}")
        return
    if _OLD_EXPAND_END not in text:
        raise SystemExit(
            f"link-all-tetras-within-rayon: ExpandPunctual fragment not found in {target}"
        )
    target.write_text(text.replace(_OLD_EXPAND_END, _NEW_EXPAND_END, 1), encoding="utf-8", newline="\n")
    print(f"link-all-tetras-within-rayon: applied in {target}")


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

    _disable_utiliser(src)
    _rewrite_fpt(src)
    _link_all_tetras(src)

    types = (src / "src" / "spps" / "sppsTypes.h").read_text(encoding="utf-8")
    core = (src / "src" / "spps" / "CalculationCore.cpp").read_text(encoding="utf-8")
    init = (src / "src" / "spps" / "sppsInitialisation.cpp").read_text(encoding="utf-8")
    if MARKER not in types and MARKER not in core:
        raise SystemExit("ERROR: patch marker missing after apply")
    if "SonoPlan: ensure every tetra that can intersect" not in init:
        raise SystemExit("ERROR: link-all-tetras patch missing after apply")
    print(f"SPPS patches OK (marker={MARKER})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
