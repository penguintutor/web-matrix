from abc import ABC, abstractmethod
from PIL import Image, ImageSequence

class DisplayTask(ABC):
    """Abstract base class for anything rendered by MatrixEngine."""

    @abstractmethod
    def setup(self, width: int, height: int) -> None:
        """Called once when the task becomes active."""
        pass

    @abstractmethod
    def render_next_frame(self) -> tuple[Image.Image | None, float]:
        """
        Returns (PIL.Image in 'RGB' mode, delay_in_seconds).
        If delay_in_seconds is 0 or negative, the frame is static and waits indefinitely.
        """
        pass


class ClearTask(DisplayTask):
    def setup(self, width: int, height: int) -> None:
        self.image = Image.new("RGB", (width, height), (0, 0, 0))

    def render_next_frame(self) -> tuple[Image.Image, float]:
        return self.image, 0.0


class StaticImageTask(DisplayTask):
    def __init__(self, image_path: str):
        self.image_path = image_path
        self.frame: Image.Image | None = None

    def setup(self, width: int, height: int) -> None:
        with Image.open(self.image_path) as img:
            # Resize to fit matrix while converting to strict RGB
            resized = img.convert("RGB").resize((width, height), Image.Resampling.NEAREST)
            self.frame = resized

    def render_next_frame(self) -> tuple[Image.Image | None, float]:
        # Return static frame and 0.0 delay (wait until interrupted)
        return self.frame, 0.0


class AnimationTask(DisplayTask):
    """Handles either a list of image paths or a multi-frame GIF."""

    def __init__(self, image_paths: list[str], fps: float = 10.0, loop: bool = True):
        self.image_paths = image_paths
        self.frame_delay = 1.0 / max(fps, 0.1)
        self.loop = loop
        self.frames: list[Image.Image] = []
        self.index = 0

    def setup(self, width: int, height: int) -> None:
        self.frames.clear()
        self.index = 0
        for path in self.image_paths:
            with Image.open(path) as img:
                if getattr(img, "is_animated", False):
                    for frame in ImageSequence.Iterator(img):
                        f_rgb = frame.convert("RGB").resize((width, height), Image.Resampling.NEAREST)
                        self.frames.append(f_rgb)
                else:
                    f_rgb = img.convert("RGB").resize((width, height), Image.Resampling.NEAREST)
                    self.frames.append(f_rgb)

    def render_next_frame(self) -> tuple[Image.Image | None, float]:
        if not self.frames:
            return None, 0.0

        frame = self.frames[self.index]
        if self.index + 1 < len(self.frames):
            self.index += 1
            return frame, self.frame_delay
        elif self.loop:
            self.index = 0
            return frame, self.frame_delay
        else:
            # Hold on last frame
            return frame, 0.0


class PluginTask(DisplayTask):
    """Wraps a dynamically loaded BasePlugin instance."""

    def __init__(self, plugin_instance, params: dict):
        self.plugin = plugin_instance
        self.params = params
        self.frame_count = 0

    def setup(self, width: int, height: int) -> None:
        self.frame_count = 0
        self.plugin.setup(width, height, self.params)

    def render_next_frame(self) -> tuple[Image.Image | None, float]:
        img, delay = self.plugin.render_frame(self.frame_count)
        self.frame_count += 1
        return img, delay