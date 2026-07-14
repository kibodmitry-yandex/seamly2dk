import xml.etree.ElementTree as ET
import re


COMMAND_RE = re.compile(r'([MmLlHhVvCcSsQqTtAaZz])')


def parse_floats(s):
    parts = re.findall(r'[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?', s)
    return [float(p) for p in parts]


def parse_path_d(d):
    # Lightweight parser for common SVG path commands used in pattern files.
    tokens = COMMAND_RE.split(d)
    tokens = [t.strip() for t in tokens if t.strip()]
    cur = (0.0, 0.0)
    start = None
    segments = []
    i = 0
    while i < len(tokens):
        cmd = tokens[i]; i += 1
        coords = []
        if i <= len(tokens)-1:
            coords = parse_floats(tokens[i]); i += 1
        rel = cmd.islower()
        op = cmd.upper()

        if op == 'M':
            # First pair is move-to, remaining pairs are implicit line-to.
            if len(coords) < 2:
                continue
            x, y = coords[0], coords[1]
            if rel:
                cur = (cur[0] + x, cur[1] + y)
            else:
                cur = (x, y)
            start = cur
            for j in range(2, len(coords) - 1, 2):
                x, y = coords[j], coords[j + 1]
                p = (cur[0] + x, cur[1] + y) if rel else (x, y)
                segments.append(('L', cur, p))
                cur = p
        elif op == 'L':
            for j in range(0, len(coords) - 1, 2):
                x, y = coords[j], coords[j + 1]
                p = (cur[0] + x, cur[1] + y) if rel else (x, y)
                segments.append(('L', cur, p))
                cur = p
        elif op == 'H':
            for x in coords:
                p = (cur[0] + x, cur[1]) if rel else (x, cur[1])
                segments.append(('L', cur, p))
                cur = p
        elif op == 'V':
            for y in coords:
                p = (cur[0], cur[1] + y) if rel else (cur[0], y)
                segments.append(('L', cur, p))
                cur = p
        elif op == 'C':
            # Cubic bezier: groups of 6 values.
            for j in range(0, len(coords) - 5, 6):
                x1, y1, x2, y2, x3, y3 = coords[j:j + 6]
                if rel:
                    p1 = (cur[0] + x1, cur[1] + y1)
                    p2 = (cur[0] + x2, cur[1] + y2)
                    p3 = (cur[0] + x3, cur[1] + y3)
                else:
                    p1 = (x1, y1)
                    p2 = (x2, y2)
                    p3 = (x3, y3)
                p0 = cur
                segments.append(('C', p0, p1, p2, p3))
                cur = p3
        elif cmd in ('Z','z'):
            if start:
                segments.append(('L', cur, start))
                cur = start
        else:
            # unsupported commands ignored
            pass
    return segments


def flatten_cubic(p0,p1,p2,p3, flatness=0.5, min_len=5.0, max_depth=24):
    # recursive subdivision
    def dist_point_line(p, a, b):
        # distance from p to line ab
        (x0,y0),(x1,y1),(x2,y2)= (p,a,b)
        dx = x2-x1; dy = y2-y1
        if dx==0 and dy==0:
            return ((x0-x1)**2+(y0-y1)**2)**0.5
        t = ((x0-x1)*dx + (y0-y1)*dy)/(dx*dx+dy*dy)
        px = x1 + t*dx; py = y1 + t*dy
        return ((x0-px)**2+(y0-py)**2)**0.5

    def recurse(a,b,c,d,depth=0):
        # flatness: max distance of control points to chord
        d1 = dist_point_line(b, a, d)
        d2 = dist_point_line(c, a, d)
        chord_len = ((d[0]-a[0])**2 + (d[1]-a[1])**2)**0.5
        # Stop when curve is flat enough, very short, or depth limit is reached.
        if max(d1,d2) <= flatness or chord_len <= min_len or depth >= max_depth:
            return [a, d]
        # subdivide
        ab = ((a[0]+b[0])/2, (a[1]+b[1])/2)
        bc = ((b[0]+c[0])/2, (b[1]+c[1])/2)
        cd = ((c[0]+d[0])/2, (c[1]+d[1])/2)
        abbc = ((ab[0]+bc[0])/2, (ab[1]+bc[1])/2)
        bccd = ((bc[0]+cd[0])/2, (bc[1]+cd[1])/2)
        mid = ((abbc[0]+bccd[0])/2, (abbc[1]+bccd[1])/2)
        left = recurse(a, ab, abbc, mid, depth + 1)
        right = recurse(mid, bccd, cd, d, depth + 1)
        return left[:-1] + right

    pts = recurse(p0,p1,p2,p3)
    return pts


def parse_svg(path):
    tree = ET.parse(path)
    root = tree.getroot()
    
    def get_element_label(elem):
        # Prefer inkscape:label (namespace-aware) when present and non-empty,
        # otherwise fall back to id or name.
        lbl = elem.get('{http://www.inkscape.org/namespaces/inkscape}label')
        if lbl and lbl.strip():
            return lbl
        lbl = elem.get('inkscape:label')
        if lbl and lbl.strip():
            return lbl
        idv = elem.get('id')
        if idv and idv.strip():
            return idv
        nm = elem.get('name')
        if nm and nm.strip():
            return nm
        return None
    # Only rely on explicit SVG curve segments; do not consult external SM2D files
    sm2d_set = set()
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    pieces = []
    # determine units: parse width (supports mm, cm, in, px, pt, pc)
    width_attr = root.get('width', '')
    viewbox = root.get('viewBox') or root.get('viewbox')
    mm_per_unit = None
    if width_attr:
        m = re.match(r"^\s*([+-]?[0-9]*\.?[0-9]+)\s*([a-zA-Z%]*)\s*$", width_attr)
        if m:
            val = float(m.group(1))
            unit = (m.group(2) or 'px').lower()
            # mm per single unit of unit type
            if unit == 'mm':
                unit_mm = 1.0
            elif unit == 'cm':
                unit_mm = 10.0
            elif unit == 'in':
                unit_mm = 25.4
            elif unit == 'pt':
                unit_mm = 25.4 / 72.0
            elif unit == 'pc':
                unit_mm = 25.4 / 6.0
            elif unit == 'px':
                unit_mm = 25.4 / 96.0
            else:
                unit_mm = None
            if unit_mm is not None:
                width_mm = val * unit_mm
                if viewbox:
                    try:
                        vb = [float(x) for x in viewbox.replace(',', ' ').split()]
                        if len(vb) == 4 and vb[2] != 0:
                            mm_per_unit = width_mm / vb[2]
                    except Exception:
                        mm_per_unit = None
                else:
                    # no viewBox: assume one user unit equals the metric unit (e.g. 1 unit == 1px/cm)
                    mm_per_unit = unit_mm
    if mm_per_unit is None:
        # last-resort fallback: treat units as mm
        mm_per_unit = 1.0
    # find groups with id or <piece> equivalents
    for g in root.findall('.//{http://www.w3.org/2000/svg}g'):
        gid = get_element_label(g)
        paths = []
        for p in g.findall('{http://www.w3.org/2000/svg}path'):
            d = p.get('d') or ''
            if not d.strip():
                continue
            segs = parse_path_d(d)
            points = []
            is_curve = False
            raw_segs = []
            for s in segs:
                if s[0] == 'L':
                    _, a, b = s
                    a_mm = (a[0]*mm_per_unit, a[1]*mm_per_unit)
                    b_mm = (b[0]*mm_per_unit, b[1]*mm_per_unit)
                    raw_segs.append(('L', a_mm, b_mm))
                    if not points:
                        points.append(a_mm)
                    points.append(b_mm)
                elif s[0] == 'C':
                    is_curve = True
                    _, p0,p1,p2,p3 = s
                    # convert control points to mm and keep raw segment
                    p0_mm = (p0[0]*mm_per_unit, p0[1]*mm_per_unit)
                    p1_mm = (p1[0]*mm_per_unit, p1[1]*mm_per_unit)
                    p2_mm = (p2[0]*mm_per_unit, p2[1]*mm_per_unit)
                    p3_mm = (p3[0]*mm_per_unit, p3[1]*mm_per_unit)
                    raw_segs.append(('C', p0_mm, p1_mm, p2_mm, p3_mm))
                    pts = flatten_cubic(p0_mm,p1_mm,p2_mm,p3_mm)
                    if not points:
                        points.append(pts[0])
                    for pt in pts[1:]:
                        points.append(pt)
                else:
                    # unsupported commands are ignored but recorded
                    raw_segs.append(('UNK', s))
            # rely only on explicit curve segments present in the SVG
            paths.append({'points': points, 'is_curve': is_curve, 'segs': raw_segs})
        if paths:
            # compute bbox in mm
            xs = [p[0] for path in paths for p in path['points']]
            ys = [p[1] for path in paths for p in path['points']]
            bbox = (min(xs), min(ys), max(xs), max(ys)) if xs and ys else (0,0,0,0)
            pieces.append({'name': gid, 'paths': paths, 'bbox_mm': bbox})
    # fallback: if no groups found, treat each top-level <path> as a separate piece
    if not pieces:
        i = 0
        for p in root.findall('.//{http://www.w3.org/2000/svg}path'):
            d = p.get('d') or ''
            if not d.strip():
                continue
            segs = parse_path_d(d)
            points = []
            is_curve = False
            raw_segs = []
            for s in segs:
                if s[0] == 'L':
                    _, a, b = s
                    a_mm = (a[0]*mm_per_unit, a[1]*mm_per_unit)
                    b_mm = (b[0]*mm_per_unit, b[1]*mm_per_unit)
                    raw_segs.append(('L', a_mm, b_mm))
                    if not points:
                        points.append(a_mm)
                    points.append(b_mm)
                elif s[0] == 'C':
                    is_curve = True
                    _, p0,p1,p2,p3 = s
                    p0_mm = (p0[0]*mm_per_unit, p0[1]*mm_per_unit)
                    p1_mm = (p1[0]*mm_per_unit, p1[1]*mm_per_unit)
                    p2_mm = (p2[0]*mm_per_unit, p2[1]*mm_per_unit)
                    p3_mm = (p3[0]*mm_per_unit, p3[1]*mm_per_unit)
                    raw_segs.append(('C', p0_mm, p1_mm, p2_mm, p3_mm))
                    pts = flatten_cubic(p0_mm,p1_mm,p2_mm,p3_mm)
                    if not points:
                        points.append(pts[0])
                    for pt in pts[1:]:
                        points.append(pt)
                else:
                    raw_segs.append(('UNK', s))

            if not points:
                continue

            # compute bbox for this single path
            xs = [pt[0] for pt in points]
            ys = [pt[1] for pt in points]
            bbox = (min(xs), min(ys), max(xs), max(ys)) if xs and ys else (0,0,0,0)

            # extract a meaningful name: prefer inkscape:label (ns-aware), then id/name, else generated
            name = get_element_label(p) or f'piece_{i}'

            pieces.append({'name': name, 'paths': [{'points': points, 'is_curve': is_curve, 'segs': raw_segs}], 'bbox_mm': bbox})
            i += 1
    return pieces
