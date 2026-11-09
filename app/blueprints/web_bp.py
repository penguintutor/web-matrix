import os
from datetime import datetime
from flask import (
    Blueprint,
    render_template,
    request,
    current_app,
    send_from_directory,
)
from werkzeug.utils import secure_filename
from app.core.matrix_engine import matrix_engine
from app.core.tasks import StaticImageTask, AnimationTask, PluginTask
from app.core.scheduler import scheduler, schedule_display_at
from app.plugins import PLUGIN_REGISTRY

web_bp = Blueprint("web", __name__)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}


def hex_to_rgb(hex_str: str) -> list[int]:
    """Convert HTML color input (#rrggbb) to [R, G, B] list."""
    h = hex_str.lstrip("#")
    if len(h) == 6:
        return [int(h[i : i + 2], 16) for i in (0, 2, 4)]
    return [255, 0, 0]


def get_uploaded_files() -> list[str]:
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    if not os.path.exists(upload_dir):
        return []
    return sorted(
        f
        for f in os.listdir(upload_dir)
        if os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS
    )


def get_formatted_jobs() -> list[dict]:
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append(
            {
                "id": job.id,
                "next_run": (
                    job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
                    if job.next_run_time
                    else "Pending"
                ),
                "task_type": job.args[0] if job.args else "unknown",
                "payload": job.args[1] if len(job.args) > 1 else {},
            }
        )
    return jobs


def render_status_alert(message: str, level: str = "success", oob: bool = False) -> str:
    """Returns a Bootstrap alert fragment (optionally with hx-swap-oob)."""
    oob_attr = 'hx-swap-oob="true"' if oob else ""
    return (
        f'<div id="status-banner" {oob_attr}>'
        f'<div class="alert alert-{level} alert-dismissible fade show py-2 mb-0" role="alert">'
        f"<strong>Matrix Status:</strong> {message}"
        f'<button type="button" class="btn-close py-2" data-bs-dismiss="alert"></button>'
        f"</div></div>"
    )


@web_bp.route("/")
def index():
    return render_template(
        "index.html",
        files=get_uploaded_files(),
        plugins=PLUGIN_REGISTRY,
        jobs=get_formatted_jobs(),
    )


@web_bp.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    """Serve uploaded images so the dashboard can render pixel-art thumbnails."""
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


# --- HTMX Media & Immediate Display Endpoints ---

@web_bp.route("/ui/upload", methods=["POST"])
def ui_upload_files():
    uploaded = request.files.getlist("files")
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    saved_count = 0

    for file in uploaded:
        if file and file.filename:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = secure_filename(file.filename)
                file.save(os.path.join(upload_dir, filename))
                saved_count += 1

    media_html = render_template("partials/media_list.html", files=get_uploaded_files())
    alert_html = render_status_alert(f"Uploaded {saved_count} file(s).", "info", oob=True)
    return media_html + alert_html


@web_bp.route("/ui/display/static/<filename>", methods=["POST"])
def ui_display_static(filename: str):
    safe_name = secure_filename(filename)
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], safe_name)
    if not os.path.isfile(path):
        return render_status_alert(f"File '{safe_name}' not found.", "danger")

    # If the file is an animated GIF, run it via AnimationTask automatically
    if safe_name.lower().endswith(".gif"):
        matrix_engine.set_task(AnimationTask([path], fps=12.0, loop=True))
        return render_status_alert(f"Playing GIF animation: {safe_name}")

    matrix_engine.set_task(StaticImageTask(path))
    return render_status_alert(f"Displaying static image: {safe_name}")


@web_bp.route("/ui/display/animation", methods=["POST"])
def ui_display_animation():
    selected_files = request.form.getlist("filenames")
    fps = float(request.form.get("fps", 10.0))
    loop = "loop" in request.form

    if not selected_files:
        return render_status_alert("Select at least one image frame for the animation.", "warning")

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    paths = [
        os.path.join(upload_dir, secure_filename(fn))
        for fn in selected_files
        if os.path.isfile(os.path.join(upload_dir, secure_filename(fn)))
    ]

    matrix_engine.set_task(AnimationTask(image_paths=paths, fps=fps, loop=loop))
    return render_status_alert(f"Running animation ({len(paths)} frames @ {fps} FPS).")


@web_bp.route("/ui/display/plugin", methods=["POST"])
def ui_display_plugin():
    plugin_name = request.form.get("plugin_name", "text_scroller")
    plugin_cls = PLUGIN_REGISTRY.get(plugin_name)
    if not plugin_cls:
        return render_status_alert(f"Plugin '{plugin_name}' not found.", "danger")

    params = {
        "text": request.form.get("text", "Hello Matrix!"),
        "color": hex_to_rgb(request.form.get("color", "#00ff80")),
        "bg_color": hex_to_rgb(request.form.get("bg_color", "#000000")),
        "fps": float(request.form.get("fps", 25.0)),
        "font_size": int(request.form.get("font_size", 16)),
    }
    matrix_engine.set_task(PluginTask(plugin_cls(), params))
    return render_status_alert(f"Running plugin '{plugin_name}': \"{params['text']}\"")


@web_bp.route("/ui/display/clear", methods=["POST"])
def ui_display_clear():
    matrix_engine.clear()
    return render_status_alert("Matrix display cleared.", "secondary")


# --- HTMX Scheduler Endpoints ---

@web_bp.route("/ui/schedule/add", methods=["POST"])
def ui_schedule_add():
    run_at_str = request.form.get("run_at", "")
    task_type = request.form.get("task_type", "plugin")

    try:
        run_date = datetime.fromisoformat(run_at_str)
    except ValueError:
        table_html = render_template("partials/schedule_list.html", jobs=get_formatted_jobs())
        alert_html = render_status_alert("Invalid date/time selected.", "danger", oob=True)
        return table_html + alert_html

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    payload = {}

    if task_type == "static":
        fn = secure_filename(request.form.get("static_filename", ""))
        payload = {"filename": fn, "image_path": os.path.join(upload_dir, fn)}
    elif task_type == "animation":
        fns = [secure_filename(f) for f in request.form.getlist("anim_filenames")]
        payload = {
            "filenames": fns,
            "image_paths": [os.path.join(upload_dir, f) for f in fns],
            "fps": float(request.form.get("anim_fps", 10.0)),
            "loop": True,
        }
    elif task_type == "plugin":
        payload = {
            "plugin_name": request.form.get("plugin_name", "text_scroller"),
            "params": {
                "text": request.form.get("plugin_text", "Scheduled Message"),
                "color": hex_to_rgb(request.form.get("plugin_color", "#ff0000")),
                "fps": float(request.form.get("plugin_fps", 25.0)),
            },
        }

    job_id = schedule_display_at(run_date, task_type, payload)
    table_html = render_template("partials/schedule_list.html", jobs=get_formatted_jobs())
    alert_html = render_status_alert(
        f"Scheduled '{task_type}' job ({job_id[:8]}) for {run_date.strftime('%Y-%m-%d %H:%M')}.",
        "success",
        oob=True,
    )
    return table_html + alert_html


@web_bp.route("/ui/schedule/delete/<job_id>", methods=["DELETE"])
def ui_schedule_delete(job_id: str):
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    table_html = render_template("partials/schedule_list.html", jobs=get_formatted_jobs())
    alert_html = render_status_alert(f"Removed scheduled job {job_id[:8]}.", "secondary", oob=True)
    return table_html + alert_html