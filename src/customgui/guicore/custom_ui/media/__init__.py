"""媒体组件（复刻 PrimeVue 的 Image / Carousel / Galleria）。"""

from .carousel import CCarousel as CCarousel
from .galleria import CGalleria as CGalleria
from .image import CImage as CImage

__all__ = ["CImage", "CCarousel", "CGalleria"]
