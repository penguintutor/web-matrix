# app/plugins/base.py
from abc import ABC, abstractmethod
from PIL import Image

class BasePlugin(ABC):
    """Base interface for all dynamic LED matrix plugins."""
    name: str = "unnamed_plugin"
    description: str = "No description provided."

    def setup(self, width: int, height: int, params: dict) -> None:
        self.width = width
        self.height = height
        self.params = params

    @abstractmethod
    def render_frame(self, frame_count: int) -> tuple[Image.Image, float]:
        """
        Generate and return (PIL.Image('RGB'), frame_delay_seconds).
        Return delay = 0.0 if only a single static frame is needed.
        """
        pass