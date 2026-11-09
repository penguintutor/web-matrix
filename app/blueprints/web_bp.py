import os
from datetime import datetime
from flask import (
    Blueprint,
    Response,
    render_template,
    request,
    redirect,
    url_for,
    current_app,
    send_from_directory,
    abort,
)
from werkzeug.utils import secure_filename
from app.core.matrix_engine import matrix_engine
from app.core.tasks import StaticImageTask, PluginTask
from app.core.sequences import sequence_manager, ALLOWED_EXTENSIONS, natural_sort_key
from app.core.scheduler import scheduler, schedule_display_at
from app.core.presets import preset_manager
from app.core.serial_controller import serial_controller
from app.plugins import PLUGIN_REGISTRY

web_bp = Blueprint("web", __name__)


def hex_to_rgb(hex_str: str) -> list[int]:
    h = hex_str.lstrip("#")
    return [int(h[i : i + 2], 16) for i in (0, 2, 4)] if len(h) == 6 else [255, 0, 0]


def get_static_images() -> list[str]:
    img_dir = current_app.config["IMAGES_FOLDER"]
    if not os.path.exists(img_dir):
        return []
    return sorted(
        (
            f
            for f in os.listdir(img_dir)
            if os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS
        ),
        key=natural_sort_key,
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
    oob_attr = 'hx-swap-oob="true"' if oob else ""
    return (
        f'<div id="status-banner" {oob_attr}>'
        f'<div class="alert alert-{level} alert-dismissible fade show py-2 mb-0" role="alert">'
        f"<strong>Matrix Status:</strong> {message}"
        f'<button type="button" class="btn-close py-2" data-bs-dismiss="alert"></button>'
        f"</div></div>"
    )


# --- Main Dashboard & Asset Serving ---

@web_bp.route("/")
def index():
    return render_template(
        "index.html",
        images=get_static_images(),
        sequences=sequence_manager.list_sequences(),
        plugins=PLUGIN_REGISTRY,
        jobs=get_formatted_jobs(),
    )


@web_bp.route("/media/images/<path:filename>")
def serve_static_image(filename: str):
    return send_from_directory(current_app.config["IMAGES_FOLDER"], filename)


@web_bp.route("/media/sequences/<seq_name>/<path:filename>")
def serve_sequence_frame(seq_name: str, filename: str):
    seq_dir = os.path.join(current_app.config["SEQUENCES_FOLDER"], secure_filename(seq_name))
    return send_from_directory(seq_dir, filename)


@web_bp.route("/ui/preview.png")
def ui_live_preview():
    png_bytes = matrix_engine.get_preview_png()
    return Response(png_bytes, mimetype="image/png", headers={"Cache-Control": "no-store"})


# --- Individual Static Image Endpoints ---

@web_bp.route("/ui/images/upload", methods=["POST"])
def ui_upload_images():
    uploaded = request.files.getlist("files")
    img_dir = current_app.config["IMAGES_FOLDER"]
    saved = 0
    for file in uploaded:
        if file and file.filename:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                fname = secure_filename(os.path.basename(file.filename))
                file.save(os.path.join(img_dir, fname))
                saved += 1

    html = render_template("partials/image_list.html", images=get_static_images())
    return html + render_status_alert(f"Uploaded {saved} individual image(s).", "info", oob=True)


@web_bp.route("/ui/display/static/<filename>", methods=["POST"])
def ui_display_static(filename: str):
    safe_name = secure_filename(filename)
    path = os.path.join(current_app.config["IMAGES_FOLDER"], safe_name)
    if not os.path.isfile(path):
        return render_status_alert(f"Image '{safe_name}' not found.", "danger")

    matrix_engine.set_task(StaticImageTask(path), label=safe_name)
    serial_controller.send_preset_list()
    return render_status_alert(f"Displaying static image: {safe_name}")


@web_bp.route("/ui/images/delete/<filename>", methods=["DELETE"])
def ui_delete_static(filename: str):
    safe_name = secure_filename(filename)
    path = os.path.join(current_app.config["IMAGES_FOLDER"], safe_name)
    if os.path.isfile(path):
        os.remove(path)
    html = render_template("partials/image_list.html", images=get_static_images())
    return html + render_status_alert(f"Deleted image '{safe_name}'.", "secondary", oob=True)


# --- Animation Sequence Endpoints & Separate Editor Page ---

@web_bp.route("/sequences")
def sequences_overview():
    """Redirects to the first available sequence editor, or shows an empty upload page."""
    seqs = sequence_manager.list_sequences()
    if seqs:
        return redirect(url_for("web.sequence_editor", seq_name=seqs[0]["name"]))
    return render_template("sequence_editor.html", sequence=None, all_sequences=[])


@web_bp.route("/sequences/<seq_name>")
def sequence_editor(seq_name: str):
    """Dedicated page for editing sequence default ms and per-frame ms overrides."""
    seq = sequence_manager.get_sequence(seq_name)
    if not seq:
        abort(404)
    return render_template(
        "sequence_editor.html",
        sequence=seq,
        all_sequences=sequence_manager.list_sequences(),
    )


@web_bp.route("/ui/sequences/upload", methods=["POST"])
def ui_upload_sequence_directory():
    """
    Accepts a directory upload (webkitdirectory) or multiple files,
    creates/updates the sequence, and redirects to its Sequence Editor page.
    """
    seq_name = request.form.get("sequence_name", "").strip()
    default_ms = int(request.form.get("default_duration_ms", 100))
    uploaded = request.files.getlist("files")

    # If sequence_name wasn't typed manually, infer it from the uploaded folder name
    if not seq_name and uploaded and uploaded[0].filename:
        parts = uploaded[0].filename.replace("\\", "/").split("/")
        seq_name = parts[0] if len(parts) > 1 else "new_sequence"

    safe_seq = secure_filename(seq_name) or "sequence"
    sequence_manager.create_or_update_from_upload(
        safe_seq, uploaded, default_duration_ms=default_ms
    )

    # Register in presets automatically so the Pico controller can select it
    preset_manager.add_preset(
        name=safe_seq, task_type="sequence", payload={"sequence_name": safe_seq}
    )
    serial_controller.send_preset_list()

    return redirect(url_for("web.sequence_editor", seq_name=safe_seq))


@web_bp.route("/ui/sequences/<seq_name>/save", methods=["POST"])
def ui_save_sequence_timings(seq_name: str):
    """Saves default_duration_ms, loop flag, and per-frame ms overrides."""
    seq = sequence_manager.get_sequence(seq_name)
    if not seq:
        abort(404)

    default_ms = int(request.form.get("default_duration_ms", 100))
    loop = "loop" in request.form

    overrides: dict[str, int | None] = {}
    for frame in seq["frames"]:
        fname = frame["filename"]
        raw_val = request.form.get(f"override_{fname}", "").strip()
        if raw_val.isdigit() and int(raw_val) > 0:
            overrides[fname] = int(raw_val)
        else:
            overrides[fname] = None

    sequence_manager.save_sequence_settings(seq_name, default_ms, loop, overrides)

    # If the user clicked "Save & Play on Matrix", trigger immediately
    if request.form.get("action") == "save_and_play":
        task = sequence_manager.build_task(seq_name)
        if task:
            matrix_engine.set_task(task, label=seq_name)

    return redirect(url_for("web.sequence_editor", seq_name=seq_name, saved="1"))


@web_bp.route("/ui/display/sequence/<seq_name>", methods=["POST"])
def ui_display_sequence(seq_name: str):
    task = sequence_manager.build_task(seq_name)
    if not task:
        return render_status_alert(f"Sequence '{seq_name}' is empty or not found.", "danger")

    matrix_engine.set_task(task, label=seq_name)
    serial_controller.send_preset_list()
    return render_status_alert(f"Playing animation sequence: {seq_name}")


@web_bp.route("/ui/sequences/<seq_name>/frame/<filename>", methods=["DELETE"])
def ui_delete_sequence_frame(seq_name: str, filename: str):
    sequence_manager.delete_frame(seq_name, filename)
    return "", 200


@web_bp.route("/ui/sequences/<seq_name>/delete", methods=["POST"])
def ui_delete_sequence(seq_name: str):
    sequence_manager.delete_sequence(seq_name)
    return redirect(url_for("web.index"))


# --- Plugin, Clear & Scheduler Endpoints ---

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
    }
    matrix_engine.set_task(PluginTask(plugin_cls(), params), label=params["text"][:16])
    return render_status_alert(f"Running plugin '{plugin_name}': \"{params['text']}\"")


@web_bp.route("/ui/display/clear", methods=["POST"])
def ui_display_clear():
    matrix_engine.clear()
    serial_controller.send_preset_list()
    return render_status_alert("Matrix display cleared.", "secondary")


@web_bp.route("/ui/schedule/add", methods=["POST"])
def ui_schedule_add():
    run_at_str = request.form.get("run_at", "")
    task_type = request.form.get("task_type", "sequence")

    try:
        run_date = datetime.fromisoformat(run_at_str)
    except ValueError:
        table_html = render_template("partials/schedule_list.html", jobs=get_formatted_jobs())
        return table_html + render_status_alert("Invalid date/time.", "danger", oob=True)

    payload = {}
    if task_type == "static":
        fn = secure_filename(request.form.get("static_filename", ""))
        payload = {
            "filename": fn,
            "image_path": os.path.join(current_app.config["IMAGES_FOLDER"], fn),
        }
    elif task_type == "sequence":
        seq_name = secure_filename(request.form.get("sequence_name", ""))
        payload = {"sequence_name": seq_name}
    elif task_type == "plugin":
        payload = {
            "plugin_name": "text_scroller",
            "params": {
                "text": request.form.get("plugin_text", "Scheduled Message"),
                "color": hex_to_rgb(request.form.get("plugin_color", "#ff0000")),
                "fps": 25.0,
            },
        }

    job_id = schedule_display_at(run_date, task_type, payload)
    table_html = render_template("partials/schedule_list.html", jobs=get_formatted_jobs())
    alert_html = render_status_alert(
        f"Scheduled '{task_type}' ({job_id[:8]}) for {run_date.strftime('%Y-%m-%d %H:%M')}.",
        "success",
        oob=True,
    )
    return table_html + alert_html


@web_bp.route("/ui/schedule/delete/<job_id>", methods=["DELETE"])
def ui_schedule_delete(job_id: str):
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    table_html = render_template("partials/schedule_list.html", jobs=get_formatted_jobs())
    return table_html + render_status_alert(f"Removed job {job_id[:8]}.", "secondary", oob=True)