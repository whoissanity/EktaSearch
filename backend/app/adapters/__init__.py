"""
app/adapters/__init__.py  —  Registry of all 8 retailer adapters.
Import ALL_ADAPTERS to fan out to every shop simultaneously.
To add a new shop: create the file, import here, append to list.
"""
from app.adapters.ryans        import RyansAdapter
from app.adapters.startech     import StarTechAdapter
from app.adapters.techland     import TechLandAdapter
from app.adapters.skyland      import SkylandAdapter
from app.adapters.vibe         import VibeAdapter
from app.adapters.techdiversity import TechDiversityAdapter
from app.adapters.blisstronics import BlisstronicsAdapter
from app.adapters.potaka       import PotakaAdapter
from app.adapters.base         import BaseRetailerAdapter

ALL_ADAPTERS: list[type[BaseRetailerAdapter]] = [
    RyansAdapter,
    StarTechAdapter,
    TechLandAdapter,
    SkylandAdapter,
    VibeAdapter,
    TechDiversityAdapter,
    BlisstronicsAdapter,
    PotakaAdapter,
]

__all__ = ["ALL_ADAPTERS", "BaseRetailerAdapter"]
