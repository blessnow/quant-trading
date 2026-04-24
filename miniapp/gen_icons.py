"""Generate tabBar icons for WeChat Mini Program — v2 with improved shapes"""
import struct, zlib, os, math

OUT = os.path.join(os.path.dirname(__file__), 'images', 'tab')
SIZE = 81

def make_png(w, h, rgba_func):
    sig = b'\x89PNG\r\n\x1a\n'
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    raw = b''
    for y in range(h):
        raw += b'\x00'
        for x in range(w):
            raw += bytes(rgba_func(x, y))
    idat = chunk(b'IDAT', zlib.compress(raw, 9))
    iend = chunk(b'IEND', b'')
    return sig + ihdr + idat + iend

def aa_blend(alpha):
    return max(0, min(255, int(alpha * 255)))

def dist(x1, y1, x2, y2):
    return math.sqrt((x-x1)**2 + (y-y1)**2) if False else 0

def sdf_circle(cx, cy, r, x, y):
    return math.sqrt((x-cx)**2 + (y-cy)**2) - r

def sdf_rounded_rect(x1, y1, x2, y2, r, x, y):
    dx = max(x1 + r - x, 0, x - (x2 - r))
    dy = max(y1 + r - y, 0, y - (y2 - r))
    return math.sqrt(dx*dx + dy*dy)

def sdf_to_alpha(d, thickness=1.5):
    if d <= -thickness: return 1.0
    if d >= thickness: return 0.0
    return 1.0 - (d + thickness) / (2 * thickness)

def sdf_segment(ax, ay, bx, by, thickness, x, y):
    dx, dy = bx-ax, by-ay
    l2 = dx*dx + dy*dy
    if l2 < 0.001: return math.sqrt((x-ax)**2 + (y-ay)**2) - thickness
    t = max(0, min(1, ((x-ax)*dx + (y-ay)*dy) / l2))
    px, py = ax + t*dx, ay + t*dy
    return math.sqrt((x-px)**2 + (y-py)**2) - thickness

def sdf_polygon(points, x, y):
    """SDF for convex polygon + winding test"""
    n = len(points)
    inside = True
    min_d = float('inf')
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i+1) % n]
        # winding
        cross = (x2-x1)*(y-y1) - (y2-y1)*(x-x1)
        if cross < 0:
            inside = False
        # edge distance
        dx, dy = x2-x1, y2-y1
        l2 = dx*dx + dy*dy
        if l2 > 0:
            t = max(0, min(1, ((x-x1)*dx + (y-y1)*dy) / l2))
            px, py = x1+t*dx, y1+t*dy
            d = math.sqrt((x-px)**2 + (y-py)**2)
            min_d = min(min_d, d)
    return -min_d if inside else min_d

# ===== Dashboard: 2x2 grid of rounded squares =====
def icon_dashboard(x, y, color):
    R, G, B = color
    a = 0.0
    s, gap, r = 26, 6, 5
    positions = [(16, 12), (16+s+gap, 12), (16, 12+s+gap), (16+s+gap, 12+s+gap)]
    for px, py in positions:
        d = sdf_rounded_rect(px, py, px+s, py+s, r, x, y)
        a = max(a, sdf_to_alpha(d))
    return (R, G, B, aa_blend(a))

# ===== Strategy: Lightning bolt =====
def icon_strategy(x, y, color):
    R, G, B = color
    bolt = [(42, 6), (24, 40), (38, 40), (32, 74), (58, 34), (44, 34), (54, 6)]
    d = sdf_polygon(bolt, x, y)
    a = sdf_to_alpha(d)
    return (R, G, B, aa_blend(a))

# ===== Article: Document with lines =====
def icon_article(x, y, color):
    R, G, B = color
    a = 0.0
    # Main document body
    d = sdf_rounded_rect(16, 8, 64, 72, 4, x, y)
    a = sdf_to_alpha(d)
    # Corner fold (subtract triangle)
    fold_pts = [(50, 8), (64, 8), (64, 22)]
    fd = sdf_polygon(fold_pts, x, y)
    fold_a = sdf_to_alpha(fd)
    if fold_a > 0 and a > 0:
        a = max(0, a - fold_a)
    # Horizontal lines (subtract)
    for ly in [34, 44, 54]:
        ld = sdf_segment(26, ly, 54, ly, 2.5, x, y)
        la = sdf_to_alpha(-ld)
        if la > 0 and a > 0:
            a = max(0, a - la * 0.95)
    return (R, G, B, aa_blend(a))

# ===== My: Person =====
def icon_my(x, y, color):
    R, G, B = color
    # Head
    hd = sdf_circle(40, 26, 13, x, y)
    # Body arc
    bd = sdf_circle(40, 82, 30, x, y)
    a_head = sdf_to_alpha(hd)
    a_body = sdf_to_alpha(bd) if y >= 42 else 0.0
    a = max(a_head, a_body)
    return (R, G, B, aa_blend(a))

COLORS = {
    'normal': (153, 153, 153),
    'selected': (26, 26, 46),
}
ICONS = {
    'dashboard': icon_dashboard,
    'strategy': icon_strategy,
    'article': icon_article,
    'my': icon_my,
}

os.makedirs(OUT, exist_ok=True)
for name, func in ICONS.items():
    for state, color in COLORS.items():
        fname = f"{name}_{'on' if state == 'selected' else 'off'}.png"
        data = make_png(SIZE, SIZE, lambda x, y, f=func, c=color: f(x, y, c))
        with open(os.path.join(OUT, fname), 'wb') as fp:
            fp.write(data)
        print(f"Created {fname} ({len(data)} bytes)")
print("Done!")
