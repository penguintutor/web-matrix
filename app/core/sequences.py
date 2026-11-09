import json
import os
import re
import shutil
from werkzeug.utils import secure_filename
from app.core.tasks import AnimationTask

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}


def natural_sort_key(filename: str) -> list:
    """Sorts filenames naturally by embedded numbers (e.g. frame_2.png before frame_10.png)."""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", filename)
    ]


class SequenceManager:
    def __init__(self):
        self.sequences_dir = ""

    def init_app(self, sequences_dir: str) -> None:
        self.sequences_dir = sequences_dir
        os.makedirs(self.sequences_dir, exist_ok=True)

    def _seq_path(self, seq_name: str) -> str:
        safe_name = secure_filename(seq_name)
        if not safe_name:
            raise ValueError("Invalid sequence name")
        return os.path.join(self.sequences_dir, safe_name)

    def _manifest_path(self, seq_name: str) -> str:
        return os.path.join(self._seq_path(seq_name), "sequence.json")

    def list_sequences(self) -> list[dict]:
        """Returns summary metadata for all animation sequences sorted by name."""
        if not os.path.exists(self.sequences_dir):
            return []
        result = []
        for entry in sorted(os.listdir(self.sequences_dir), key=natural_sort_key):
            full_path = os.path.join(self.sequences_dir, entry)
            if os.path.isdir(full_path):
                data = self.get_sequence(entry)
                if data and data["frames"]:
                    result.append(data)
        return result

    def get_sequence(self, seq_name: str) -> dict | None:
        """
        Loads the sequence manifest and returns ordered frame metadata:
        {
          "name": str,
          "default_duration_ms": int,
          "loop": bool,
          "total_duration_ms": int,
          "first_frame": str | None,
          "frames": [
              {
                  "filename": str,
                  "override_ms": int | None,
                  "effective_ms": int
              }, ...
          ]
        }
        """
        seq_dir = self._seq_path(seq_name)
        if not os.path.isdir(seq_dir):
            return None

        manifest = {
            "name": seq_name,
            "default_duration_ms": 100,
            "loop": True,
            "frame_overrides": {},
        }
        m_path = self._manifest_path(seq_name)
        if os.path.isfile(m_path):
            try:
                with open(m_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    manifest.update(loaded)
            except Exception:
                pass

        default_ms = int(manifest.get("default_duration_ms", 100))
        overrides: dict = manifest.get("frame_overrides", {})

        # Scan directory and sort files by filename
        image_files = sorted(
            (
                f
                for f in os.listdir(seq_dir)
                if os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS
            ),
            key=natural_sort_key,
        )

        frames = []
        total_ms = 0
        for fname in image_files:
            override_val = overrides.get(fname)
            override_ms = int(override_val) if override_val is not None else None
            effective_ms = override_ms if override_ms is not None else default_ms
            total_ms += effective_ms
            frames.append(
                {
                    "filename": fname,
                    "override_ms": override_ms,
                    "effective_ms": effective_ms,
                }
            )

        return {
            "name": seq_name,
            "default_duration_ms": default_ms,
            "loop": bool(manifest.get("loop", True)),
            "total_duration_ms": total_ms,
            "first_frame": frames[0]["filename"] if frames else None,
            "frames": frames,
        }

    def save_sequence_settings(
        self,
        seq_name: str,
        default_duration_ms: int,
        loop: bool,
        frame_overrides: dict[str, int | None],
    ) -> None:
        """Saves default duration (ms), loop setting, and per-frame ms overrides."""
        seq_dir = self._seq_path(seq_name)
        os.makedirs(seq_dir, exist_ok=True)

        # Keep only positive integer overrides; omit frames using the default duration
        cleaned_overrides = {
            fname: int(ms)
            for fname, ms in frame_overrides.items()
            if ms is not None and int(ms) > 0
        }

        manifest = {
            "name": seq_name,
            "default_duration_ms": max(10, int(default_duration_ms)),
            "loop": bool(loop),
            "frame_overrides": cleaned_overrides,
        }
        with open(self._manifest_path(seq_name), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def create_or_update_from_upload(
        self, seq_name: str, uploaded_files: list, default_duration_ms: int = 100
    ) -> int:
        """Saves uploaded directory/multiple files into the sequence folder."""
        safe_seq = secure_filename(seq_name)
        seq_dir = self._seq_path(safe_seq)
        os.makedirs(seq_dir, exist_ok=True)

        saved_count = 0
        for file in uploaded_files:
            if file and file.filename:
                # webkitdirectory submits relative path "folder/frame_01.png"; strip folder prefix
                base_name = os.path.basename(file.filename.replace("\\", "/"))
                ext = os.path.splitext(base_name)[1].lower()
                if ext in ALLOWED_EXTENSIONS:
                    safe_fname = secure_filename(base_name)
                    file.save(os.path.join(seq_dir, safe_fname))
                    saved_count += 1

        # Create sequence.json if this is a brand new sequence
        if not os.path.isfile(self._manifest_path(safe_seq)):
            self.save_sequence_settings(
                safe_seq, default_duration_ms=default_duration_ms, loop=True, frame_overrides={}
            )
        return saved_count

    def delete_frame(self, seq_name: str, filename: str) -> None:
        seq_dir = self._seq_path(seq_name)
        safe_fname = secure_filename(filename)
        fpath = os.path.join(seq_dir, safe_fname)
        if os.path.isfile(fpath):
            os.remove(fpath)

    def delete_sequence(self, seq_name: str) -> None:
        seq_dir = self._seq_path(seq_name)
        if os.path.isdir(seq_dir):
            shutil.rmtree(seq_dir)

    def build_task(self, seq_name: str) -> AnimationTask | None:
        """Creates an AnimationTask with resolved per-frame millisecond timings."""
        seq = self.get_sequence(seq_name)
        if not seq or not seq["frames"]:
            return None

        seq_dir = self._seq_path(seq_name)
        schedule = [
            (os.path.join(seq_dir, f["filename"]), f["effective_ms"])
            for f in seq["frames"]
        ]
        return AnimationTask(frame_schedule=schedule, loop=seq["loop"])


sequence_manager = SequenceManager()