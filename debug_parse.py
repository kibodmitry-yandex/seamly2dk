import json
from svg_parser import parse_svg
p = parse_svg(r'i:\seamly2dk\polo\polo_pieces.svg')
out = []
for i, piece in enumerate(p):
    paths_info = []
    for j, path in enumerate(piece.get('paths', [])):
        paths_info.append({
            'path_index': j,
            'is_curve': bool(path.get('is_curve')),
            'segs_types': [s[0] for s in path.get('segs', [])],
            'num_points': len(path.get('points', []))
        })
    out.append({'piece_index': i, 'name': piece.get('name'), 'paths': paths_info})
print(json.dumps(out, indent=2))
