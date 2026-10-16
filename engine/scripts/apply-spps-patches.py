#!/usr/bin/env python3
"""Apply SonoPlan SPPS source patches to a checked-out I-Simpa tree.

Prefers ``git apply`` for ``engine/patches/*.patch``. Falls back to an exact
string replace for the known UTILISER deposit fix when the hunk context
cannot match (e.g. CRLF / line-number drift).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
PATCH_DIR = ENGINE_DIR / "patches"

# Exact fragment from I-Simpa 929a5c8e… src/spps/CalculationCore.cpp
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
	// Upstream UTILISER path only deposited on the *end* tetra; particles that
	// leave a linked tetra in one timestep wrote zero punctual energy while
	// still hitting walls (minimal_room CI).
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


def _apply_deposit_fix(src: Path) -> None:
    target = src / "src" / "spps" / "CalculationCore.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
    if _NEW_FPT in text:
        print(f"deposit-on-start-tetra: already applied in {target}")
        return
    if _OLD_FPT not in text:
        raise SystemExit(
            f"deposit-on-start-tetra: expected FreeParticleTranslation fragment "
            f"not found in {target} (pinned commit mismatch?)"
        )
    target.write_text(text.replace(_OLD_FPT, _NEW_FPT, 1), encoding="utf-8", newline="\n")
    print(f"deposit-on-start-tetra: applied string replace in {target}")


def _apply_link_all_tetras(src: Path) -> None:
    target = src / "src" / "spps" / "sppsInitialisation.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
    if "SonoPlan: ensure every tetra that can intersect" in text:
        print(f"link-all-tetras-within-rayon: already applied in {target}")
        return
    if _OLD_EXPAND_END not in text:
        raise SystemExit(
            f"link-all-tetras-within-rayon: expected ExpandPunctual fragment "
            f"not found in {target} (pinned commit mismatch?)"
        )
    target.write_text(text.replace(_OLD_EXPAND_END, _NEW_EXPAND_END, 1), encoding="utf-8", newline="\n")
    print(f"link-all-tetras-within-rayon: applied string replace in {target}")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print(f"usage: {Path(__file__).name} <isimpa-src-dir>", file=sys.stderr)
        return 2
    src = Path(args[0]).resolve()
    if not (src / "src" / "spps" / "CalculationCore.cpp").is_file():
        print(f"ERROR: not an I-Simpa tree: {src}", file=sys.stderr)
        return 1

    patches = sorted(PATCH_DIR.glob("*.patch"))
    for patch in patches:
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
            print(f"  git apply failed ({r.returncode}); using string fallback")
            if r.stderr:
                print(r.stderr[:500])

    # Always ensure string-replace fixes are present (idempotent).
    _apply_deposit_fix(src)
    _apply_link_all_tetras(src)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
