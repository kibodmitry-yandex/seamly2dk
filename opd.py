def build_opd(points, origin='center'):
    """
    Build OPD text from points.
    Input points are expected in millimetres (mm). OPD requires centimetres (cm)
    and a coordinate system with Y increasing upwards (bottom-up). This function
    converts mm->cm and flips the Y axis so OPD is oriented bottom-up.
    origin: 'center' or 'topleft' to choose the reference point for translation.
    """
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    if origin == 'center':
        ox = (minx + maxx) / 2.0
        oy = (miny + maxy) / 2.0
    elif origin == 'topleft':
        ox, oy = minx, miny
    else:
        ox, oy = minx, miny

    lines = ['OPD']
    for x_mm, y_mm in points:
        # translate relative to origin (still mm)
        dx = x_mm - ox
        dy = y_mm - oy
        # flip Y so positive is upward (OPD expects bottom-up)
        dy = -dy
        # convert mm -> cm
        tx_cm = dx / 10.0
        ty_cm = dy / 10.0
        lines.append(f'{tx_cm:.3f}\t{ty_cm:.3f}')
    return '\n'.join(lines)
