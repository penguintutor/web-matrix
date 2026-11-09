from abc import ABC, abstractmethod
from PIL import Image, ImageOps

def fit_to_matrix(img: Image.Image, width: int, height: int, mode: str = "pad") -> Image.Image:
    """
    Resizes an image to fit the target matrix dimensions using crisp pixel scaling.
    - 'pad': Preserves aspect ratio and centers with black (off) LEDs if ratio differs.
    - 'stretch': Forces image to fill full width x height.
    - 'center': Keeps 1:1 original pixel size if smaller than matrix, centered on black.
    """
    rgb_img = img.convert("RGB")
    if rgb_img.size == (width, height):
        return rgb_img

    if mode == "stretch":
        return rgb_img.resize((width, height), Image.Resampling.NEAREST)
    elif mode == "center" and rgb_img.width <= width and rgb_img.height <= height:
        canvas = Image.new("RGB", (width, height), (0, 0, 0))
        x = (width - rgb_img.width) // 2
        y = (height - rgb_img.height) // 2
        canvas.paste(rgb_img, (x, y))
        return canvas
    else:
        # Default 'pad': scales up/down to fit while preserving aspect ratio
        return ImageOps.pad(
            rgb_img,
            (width, height),
            method=Image.Resampling.NEAREST,
            color=(0, 0, 0),
            centering=(0.5, 0.5),
        )

class DisplayTask(ABC):
    @abstractmethod
    def setup(self, width: int, height: int) -> None:
        pass

    @abstractmethod
    def render_next_frame(self) -> tuple[Image.Image | None, float]:
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
            self.frame = fit_to_matrix(img, width, height, mode="pad")

    def render_next_frame(self) -> tuple[Image.Image | None, float]:
        return self.frame, 0.0


class AnimationTask(DisplayTask):
    """
    Plays an ordered sequence of frames where each frame has its own duration in milliseconds.
    frame_schedule: list of (image_path, duration_ms) tuples.
    """

    def __init__(self, frame_schedule: list[tuple[str, int]], loop: bool = True):
        self.frame_schedule = frame_schedule
        self.loop = loop
        # Loaded in setup(): list of (PIL.Image, delay_seconds)
        self.frames: list[tuple[Image.Image, float]] = []
        self.index = 0

    def setup(self, width: int, height: int) -> None:
        self.frames.clear()
        self.index = 0
        for path, duration_ms in self.frame_schedule:
            delay_sec = max(int(duration_ms), 10) / 1000.0  # Minimum 10ms safety floor
            with Image.open(path) as img:
                f_rgb = img.convert("RGB").resize((width, height), Image.Resampling.NEAREST)
                self.frames.append((f_rgb, delay_sec))

    def render_next_frame(self) -> tuple[Image.Image | None, float]:
        if not self.frames:
            return None, 0.0

        frame_img, delay_sec = self.frames[self.index]

        if self.index + 1 < len(self.frames):
            self.index += 1
            return frame_img, delay_sec
        elif self.loop:
            self.index = 0
            return frame_img, delay_sec
        else:
            # Non-looping sequence: hold indefinitely on the final frame
            return frame_img, 0.0


class PluginTask(DisplayTask):
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