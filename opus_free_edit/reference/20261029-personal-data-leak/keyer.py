import numpy as np
# garbage matte: only x in [GX0,GX1) of the 1920x1080 camera frame can contain the presenter
GX0, GX1 = 400, 1480
def key(rgb):
    """rgb uint8 HxWx3 (camera crop) -> (fg float32 HxWx3 despilled, alpha float32 HxW)"""
    f = rgb.astype(np.float32)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    mx = np.maximum(r, b)
    gs = g - mx                      # greenness
    # luma-relative greenness handles the shadows on the cloth
    rel = gs / (g + 8.0)
    a = 1.0 - np.clip((rel - 0.12) / (0.30 - 0.12), 0, 1)
    # despill: limit green to the max of red/blue (slightly above)
    g2 = np.minimum(g, mx * 1.02 + 2)
    fg = np.stack([r, g2, b], -1)
    return fg, a
