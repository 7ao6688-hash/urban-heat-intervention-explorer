from dataclasses import dataclass
import numpy as np

CLASSES = {1: "Built-up", 2: "Water", 3: "Forest", 4: "Grassland"}

@dataclass(frozen=True)
class UrbanScene:
    red: np.ndarray
    nir: np.ndarray
    lst_c: np.ndarray
    land_cover: np.ndarray
    resolution_m: float = 30.0
    provenance: str = "synthetic demonstration data"

def make_synthetic_scene(seed: int = 42) -> UrbanScene:
    """Create a deterministic Glasgow-like urban raster for software demonstration."""
    rng = np.random.default_rng(seed); h, w = 120, 150; y, x = np.mgrid[:h, :w]
    centre = np.exp(-(((x-w*.52)/35)**2 + ((y-h*.53)/29)**2)); river = np.abs(y-(h*.55+7*np.sin(x/20))) < 2
    forest = ((x < 32) & (y > 18)) | ((x > 112) & (y < 62)); grass = ((y < 22) | (y > 102) | ((x < 58) & (y > 76))) & ~forest
    cover = np.where(river, 2, np.where(forest, 3, np.where(grass, 4, 1))).astype(int)
    ndvi_base = {1: .13, 2: -.08, 3: .58, 4: .40}; ndvi = np.zeros((h,w))
    for key, value in ndvi_base.items(): ndvi[cover == key] = value
    ndvi = np.clip(ndvi + .08*np.sin(x/13)*np.cos(y/17) + rng.normal(0,.025,(h,w)), -.2, .82)
    lst = 27.4 - 11.4*ndvi + 2.8*centre + rng.normal(0,.65,(h,w)); lst[river] -= 2.0
    # Construct reflectance pair satisfying NDVI = (NIR-red)/(NIR+red).
    total = .34 + rng.normal(0,.018,(h,w)); red = total*(1-ndvi)/2; nir = total*(1+ndvi)/2
    return UrbanScene(red=np.maximum(red,.001), nir=np.maximum(nir,.001), lst_c=lst, land_cover=cover)
