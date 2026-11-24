"""猕猴桃桌面宠物：基座原生常驻宠物。"""

from __future__ import annotations

from .controller import MihoutaoPetController as MihoutaoPetController
from .events import PetEventBus as PetEventBus
from .events import pet_bus as pet_bus
from .pet_window import PetWindow as PetWindow

__all__ = ["MihoutaoPetController", "PetEventBus", "PetWindow", "pet_bus"]
