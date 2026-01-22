from dataclasses import dataclass
from typing import Optional


@dataclass
class BotEvent:
    symbol: str
    level: str  # INFO / WARNING / ERROR / CRITICAL
    message: str
    data: Optional[dict] = None