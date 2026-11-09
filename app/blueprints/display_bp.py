import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from app.core.matrix_engine import matrix_engine
from app.core.tasks import StaticImageTask, AnimationTask

display_bp = Blueprint("display", __name__, url_prefix="/api/display")


@display_bp.route("/image", methods=["POST"])
def display_static_image():
    """Upload or reference an image to display immediately."""
    if "file" in request.files:
        file = request.files["file"]
        filename = secure_filename(file.filename)
        save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        file.save(save_path)
    else:
        data = request.get_json(silent=True) or {}
        filename = secure_filename(data.get("filename", ""))
        save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        if not os.path.isfile(save_path):
            return jsonify({"error": "File not found in uploads directory"}), 404

    matrix_engine.set_task(StaticImageTask(save_path))
    return jsonify({"status": "displaying_image", "file": filename})


@display_bp.route("/animation", methods=["POST"])
def display_animation():
    """
    Trigger an animation from a list of uploaded filenames or multi-file upload.
    JSON Body: {"filenames": ["frame1.png", "frame2.png"], "fps": 12, "loop": true}
    """
    data = request.get_json(silent=True) or {}
    filenames = data.get("filenames", [])
    fps = float(data.get("fps", 10.0))
    loop = bool(data.get("loop", True))

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    paths = [os.path.join(upload_dir, secure_filename(fn)) for fn in filenames]
    missing = [p for p in paths if not os.path.isfile(p)]
    if not paths or missing:
        return jsonify({"error": "Missing or invalid frame files", "missing": missing}), 400

    matrix_engine.set_task(AnimationTask(image_paths=paths, fps=fps, loop=loop))
    return jsonify({"status": "displaying_animation", "frames": len(paths), "fps": fps})


@display_bp.route("/clear", methods=["POST"])
def clear_display():
    matrix_engine.clear()
    return jsonify({"status": "cleared"})