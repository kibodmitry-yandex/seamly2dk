import xml.etree.ElementTree as ET
import re


COMMAND_RE = re.compile(r'([MmLlHhVvCcSsQqTtAaZz])')


def parse_floats(s):
    parts = re.findall(r'[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?', s)
    return [float(p) for p in parts]


def parse_path_d(d):
    # Very small parser: handle M, L, C, Z. Return list of segments; curves will be flattened.
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
        if cmd in ('M','m'):
            x,y = coords[0], coords[1]
            cur = (x,y)
            start = cur
            # treat M as move
        elif cmd in ('L','l'):
            pts = []
            for j in range(0,len(coords),2):
                x,y = coords[j], coords[j+1]
                pts.append((x,y))
            for p in pts:
                segments.append(('L', cur, p))
                cur = p
        elif cmd in ('C','c'):
            # cubic bezier: groups of 6
            for j in range(0,len(coords),6):
                x1,y1,x2,y2,x3,y3 = coords[j:j+6]
                p0 = cur; p1=(x1,y1); p2=(x2,y2); p3=(x3,y3)
                segments.append(('C', p0,p1,p2,p3))
                cur = p3
        elif cmd in ('Z','z'):
            if start:
                segments.append(('L', cur, start))
                cur = start
        else:
            # unsupported commands ignored
            pass
    return segments


def flatten_cubic(p0,p1,p2,p3, flatness=0.5, min_len=5.0):
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

    def recurse(a,b,c,d):
        # flatness: max distance of control points to chord
        d1 = dist_point_line(b, a, d)
        d2 = dist_point_line(c, a, d)
        chord_len = ((d[0]-a[0])**2 + (d[1]-a[1])**2)**0.5
        if max(d1,d2) <= flatness and chord_len >= min_len:
            return [a, d]
        # subdivide
        ab = ((a[0]+b[0])/2, (a[1]+b[1])/2)
        bc = ((b[0]+c[0])/2, (b[1]+c[1])/2)
        cd = ((c[0]+d[0])/2, (c[1]+d[1])/2)
        abbc = ((ab[0]+bc[0])/2, (ab[1]+bc[1])/2)
        bccd = ((bc[0]+cd[0])/2, (bc[1]+cd[1])/2)
        mid = ((abbc[0]+bccd[0])/2, (abbc[1]+bccd[1])/2)
        left = recurse(a, ab, abbc, mid)
        right = recurse(mid, bccd, cd, d)
        return left[:-1] + right

    pts = recurse(p0,p1,p2,p3)
    return pts


def parse_svg(path):
    tree = ET.parse(path)
    root = tree.getroot()
    # Only rely on explicit SVG curve segments; do not consult external SM2D files
    sm2d_set = set()
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    pieces = []
    # determine units: if width contains mm and viewBox present, compute mm per viewBox unit
    width_attr = root.get('width', '')
    viewbox = root.get('viewBox') or root.get('viewbox')
    mm_per_unit = None
    if width_attr and width_attr.endswith('mm') and viewbox:
        try:
            width_mm = float(width_attr[:-2])
            vb = [float(x) for x in viewbox.replace(',', ' ').split()]
            if len(vb) == 4:
                vb_w = vb[2]
                if vb_w != 0:
                    mm_per_unit = width_mm / vb_w
        except Exception:
            mm_per_unit = None
    if mm_per_unit is None:
        # fallback: assume units are mm already
        mm_per_unit = 1.0
    # find groups with id or <piece> equivalents
    for g in root.findall('.//{http://www.w3.org/2000/svg}g'):
        gid = g.get('id') or g.get('inkscape:label') or g.get('name')
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
    # fallback: parse top-level paths
    if not pieces:
        paths = []
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
            paths.append({'points': points, 'is_curve': is_curve, 'segs': raw_segs})
        if paths:
            xs = [p[0] for path in paths for p in path['points']]
            ys = [p[1] for path in paths for p in path['points']]
            bbox = (min(xs), min(ys), max(xs), max(ys)) if xs and ys else (0,0,0,0)
            pieces.append({'name': 'layer0', 'paths': paths, 'bbox_mm': bbox})
    return pieces
