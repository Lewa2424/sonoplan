"""SonoPlan SPPS adapter (STG-01 stub).

Pipeline (ENG-003): snapshot → surfaces → mesh → TetGen → mesh/XML → SPPS →
validate → normalize → manifest.

JSON project is never fed directly to SPPS (ENG-005).
Exit code 0 alone is never success (ENG-009).
"""

__version__ = "0.1.0-stg01"
