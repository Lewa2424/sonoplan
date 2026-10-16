#!/usr/bin/env python3
"""Apply SonoPlan SPPS source patches to a checked-out I-Simpa tree.

Hard rules:
- Never undefine UTILISER_MAILLAGE_OPTIMISATION: the upstream #ifndef path does
  not compile against current core types (doInvertNormal / percCollision).
- Prefer ``git apply`` of ``engine/patches/*.patch`` on pinned commit 929a5c8e.
- String fallback only for the known ExpandPunctual + marker edits (idempotent).
- Do not rewrite FreeParticleTranslation: under UTILISER the active path already
  calls ParticuleFreeTranslation; rewriting the #ifndef body is dead/misleading.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
PATCH_DIR = ENGINE_DIR / "patches"
MARKER = "sonoplan-link-all-tetras-v1"

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
    print(f"link-all-tetras-within-rayon: applied string replace in {target}")


def _embed_marker(src: Path) -> None:
    target = src / "src" / "spps" / "CalculationCore.cpp"
    text = target.read_text(encoding="utf-8", errors="replace")
    if MARKER in text:
        print(f"patch-marker: already present in {target}")
        return
    needle = '#include "CalculationCore.h"'
    if needle not in text:
        raise SystemExit(f"patch-marker: include missing in {target}")
    text = text.replace(
        needle,
        needle + f'\nstatic const char sonoplan_spps_patch[] = "{MARKER}";\n',
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

    types = (src / "src" / "spps" / "sppsTypes.h").read_text(encoding="utf-8")
    if "#define UTILISER_MAILLAGE_OPTIMISATION" not in types:
        raise SystemExit(
            "ERROR: UTILISER_MAILLAGE_OPTIMISATION must stay defined "
            "(ifndef FreeParticleTranslation path does not compile)"
        )

    apply_failed: list[str] = []
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
            apply_failed.append(patch.name)
            print(f"  git apply failed ({r.returncode}); string fallbacks follow")
            if r.stderr:
                print(r.stderr[:400])

    _link_all_tetras(src)
    _embed_marker(src)

    init = (src / "src" / "spps" / "sppsInitialisation.cpp").read_text(encoding="utf-8")
    core = (src / "src" / "spps" / "CalculationCore.cpp").read_text(encoding="utf-8")
    if "SonoPlan: ensure every tetra that can intersect" not in init:
        raise SystemExit("ERROR: link-all-tetras patch missing after apply")
    if MARKER not in core:
        raise SystemExit("ERROR: patch marker missing after apply")
    if "#define UTILISER_MAILLAGE_OPTIMISATION" not in (
        src / "src" / "spps" / "sppsTypes.h"
    ).read_text(encoding="utf-8"):
        raise SystemExit("ERROR: UTILISER was disabled during patch apply")

    if apply_failed:
        print(
            f"WARNING: git apply missed {apply_failed}; string fallback recovered. "
            "Regenerate patches for a clean apply on the pinned commit."
        )
    print(f"SPPS patches OK (marker={MARKER}, UTILISER kept, git_apply_miss={apply_failed or 'none'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
