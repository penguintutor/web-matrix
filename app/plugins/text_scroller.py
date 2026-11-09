import os
from PIL import Image, ImageDraw, ImageFont, BdfFontFile
from app.plugins.base import BasePlugin


def load_matrix_font(font_path: str | None, font_size: int = 16):
    """
    Loads a .bdf bitmap font (converting and caching it for Pillow if needed),
    a .pil bitmap font, or a .ttf font.
    """
    if not font_path or not os.path.isfile(font_path):
        return ImageFont.load_default()

    ext = os.path.splitext(font_path)[1].lower()
    if ext == ".bdf":
        # Convert X11 .bdf font into Pillow's native .pil + .pbm format if not cached
        pil_path = os.path.splitext(font_path)[0] + ".pil"
        if not os.path.isfile(pil_path):
            with open(font_path, "rb") as fp:
                bdf = BdfFontFile.BdfFontFile(fp)
                bdf.save(os.path.splitext(font_path)[0])
        return ImageFont.load(pil_path)
    elif ext == ".pil":
        return ImageFont.load(font_path)
    else:
        return ImageFont.truetype(font_path, font_size)


class TextScrollerPlugin(BasePlugin):
    name = "text_scroller"
    description = "Scrolls crisp bitmap (.bdf) or TrueType text across the matrix."

    def setup(self, width: int, height: int, params: dict) -> None:
        super().setup(width, height, params)
        self.text = str(params.get("text", "Hello Matrix!"))
        self.color = tuple(params.get("color", [255, 0, 0]))
        self.bg_color = tuple(params.get("bg_color", [0, 0, 0]))
        fps = float(params.get("fps", 25.0))
        self.delay = 1.0 / max(fps, 1.0)

        font_path = params.get("font_path")
        font_size = int(params.get("font_size", 16))
        try:
            self.font = load_matrix_font(font_path, font_size)
        except Exception:
            self.font = ImageFont.load_default()

        # Measure exact pixel bounding box so vertical alignment is centered properly
        scratch = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(scratch)
        draw.fontmode = "1"  # Disable anti-aliasing for sharp pixel edges
        bbox = draw.textbbox((0, 0), self.text, font=self.font)
        self.text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        self.x_pos = width
        # Offset by bbox[1] so fonts with top ascender padding (like 10x20.bdf) center cleanly
        self.y_pos = ((height - text_height) // 2) - bbox[1]

    def render_frame(self, frame_count: int) -> tuple[Image.Image, float]:
        img = Image.new("RGB", (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        draw.fontmode = "1"  # Force crisp 1-bit pixel edges
        draw.text((self.x_pos, self.y_pos), self.text, font=self.font, fill=self.color)

        self.x_pos -= 1
        if self.x_pos < -self.text_width:
            self.x_pos = self.width

        return img, self.delay