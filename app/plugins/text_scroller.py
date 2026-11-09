from PIL import Image, ImageDraw, ImageFont
from app.plugins.base import BasePlugin

class TextScrollerPlugin(BasePlugin):
    name = "text_scroller"
    description = "Scrolls a custom text message across the matrix."

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
            self.font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
        except OSError:
            self.font = ImageFont.load_default()

        # Measure text width using a scratch draw context
        scratch = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(scratch)
        bbox = draw.textbbox((0, 0), self.text, font=self.font)
        self.text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        self.x_pos = width
        self.y_pos = max(0, (height - text_height) // 2)

    def render_frame(self, frame_count: int) -> tuple[Image.Image, float]:
        img = Image.new("RGB", (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        draw.text((self.x_pos, self.y_pos), self.text, font=self.font, fill=self.color)

        self.x_pos -= 1
        if self.x_pos < -self.text_width:
            self.x_pos = self.width

        return img, self.delay