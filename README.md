seamly2dk — OPD exporter (MVP)

This is an initial MVP skeleton for converting SVG/Seamly2D paths to OPD format for DesignaKnit8.

Run:

python main.py

Features in this skeleton:
- Open an SVG file
- Parse simple paths (M, L, C)
- Flatten cubic beziers to polylines (basic)
- Display pieces and copy OPD for the first path
