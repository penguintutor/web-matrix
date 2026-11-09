import json
import os
import logging
from app.core.matrix_engine import matrix_engine
from app.core.tasks import StaticImageTask, AnimationTask, PluginTask, ClearTask
from app.plugins import PLUGIN_REGISTRY
from app.core.sequences import sequence_manager

logger = logging.getLogger(__name__)

DEFAULT_PRESETS = [
    {
        "name": "Silverstone",
        "task_type": "plugin",
        "payload": {
            "plugin_name": "text_scroller",
            "params": {
                "text": "Hello Silverstone!",
                "color": [0, 255, 128],
                "bg_color": [0, 0, 0],
                "fps": 30,
                "font_path": "fonts/10x20.bdf",
            },
        },
    },
    {
        "name": "Merry Xmas",
        "task_type": "plugin",
        "payload": {
            "plugin_name": "text_scroller",
            "params": {
                "text": "Merry Christmas!",
                "color": [255, 30, 30],
                "bg_color": [0, 20, 0],
                "fps": 25,
                "font_path": "fonts/10x20.bdf",
            },
        },
    },
    {
        "name": "Clear Screen",
        "task_type": "clear",
        "payload": {},
    },
]


class PresetManager:
    def __init__(self):
        self.presets_file = ""
        self.upload_folder = ""
        self.presets: list[dict] = []

    def init_app(self, presets_file: str, upload_folder: str) -> None:
        self.presets_file = presets_file
        self.upload_folder = upload_folder
        if not os.path.exists(self.presets_file):
            self.presets = DEFAULT_PRESETS
            self.save()
        else:
            self.load()

    def load(self) -> list[dict]:
        try:
            with open(self.presets_file, "r", encoding="utf-8") as f:
                self.presets = json.load(f)
        except Exception as exc:
            logger.error(f"Failed to load presets: {exc}")
            self.presets = DEFAULT_PRESETS
        return self.presets

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.presets_file), exist_ok=True)
        with open(self.presets_file, "w", encoding="utf-8") as f:
            json.dump(self.presets, f, indent=2)

    def add_preset(self, name: str, task_type: str, payload: dict) -> None:
        # Replace if preset with same name exists
        self.presets = [p for p in self.presets if p["name"] != name]
        self.presets.append({"name": name[:18], "task_type": task_type, "payload": payload})
        self.save()

    def delete_preset(self, index: int) -> None:
        if 0 <= index < len(self.presets):
            self.presets.pop(index)
            self.save()

    def trigger_preset(self, index: int) -> str | None:
        """Activates the preset by index on the MatrixEngine and returns its name."""
        if not (0 <= index < len(self.presets)):
            return None

        preset = self.presets[index]
        name = preset["name"]
        t_type = preset["task_type"]
        payload = preset.get("payload", {})

        if t_type == "static":
            path = payload.get("image_path") or os.path.join(self.upload_folder, payload.get("filename", ""))
            if path.lower().endswith(".gif"):
                matrix_engine.set_task(AnimationTask([path], fps=12.0, loop=True), label=name)
            else:
                matrix_engine.set_task(StaticImageTask(path), label=name)
        elif t_type == "animation":
            paths = payload.get("image_paths") or [
                os.path.join(self.upload_folder, fn) for fn in payload.get("filenames", [])
            ]
            matrix_engine.set_task(
                AnimationTask(paths, fps=payload.get("fps", 10.0), loop=payload.get("loop", True)),
                label=name,
            )
        elif t_type == "sequence":
            seq_name = payload["sequence_name"]
            task = sequence_manager.build_task(seq_name)
            if task:
                matrix_engine.set_task(task, label=seq_name)
        elif t_type == "plugin":
            plugin_cls = PLUGIN_REGISTRY.get(payload.get("plugin_name", "text_scroller"))
            if plugin_cls:
                matrix_engine.set_task(PluginTask(plugin_cls(), payload.get("params", {})), label=name)
        elif t_type == "clear":
            matrix_engine.set_task(ClearTask(), label="Cleared")

        return name


preset_manager = PresetManager()