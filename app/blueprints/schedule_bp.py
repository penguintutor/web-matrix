import os
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from app.core.scheduler import scheduler, schedule_display_at

schedule_bp = Blueprint("schedule", __name__, url_prefix="/api/schedule")


@schedule_bp.route("/", methods=["GET"])
def list_scheduled_jobs():
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "task_type": job.args[0] if job.args else None,
            "payload": job.args[1] if len(job.args) > 1 else None,
        })
    return jsonify({"scheduled_jobs": jobs})


@schedule_bp.route("/add", methods=["POST"])
def add_scheduled_job():
    """
    Schedule a display task in the future.
    Example JSON:
    {
        "run_at": "2026-11-15T18:30:00",
        "task_type": "plugin",
        "payload": {
            "plugin_name": "text_scroller",
            "params": {"text": "Scheduled Hello!", "color": [0, 255, 0]}
        }
    }
    """
    data = request.get_json(silent=True) or {}
    run_at_str = data.get("run_at")
    task_type = data.get("task_type")
    payload = data.get("payload", {})

    if not run_at_str or task_type not in ("static", "animation", "plugin", "clear"):
        return jsonify({"error": "Invalid 'run_at' ISO timestamp or 'task_type'"}), 400

    try:
        run_date = datetime.fromisoformat(run_at_str)
    except ValueError:
        return jsonify({"error": "Invalid ISO 8601 format for 'run_at'"}), 400

    # Normalize relative filenames inside static/animation payloads
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    if task_type == "static" and "filename" in payload:
        payload["image_path"] = os.path.join(upload_dir, secure_filename(payload["filename"]))
    elif task_type == "animation" and "filenames" in payload:
        payload["image_paths"] = [
            os.path.join(upload_dir, secure_filename(fn)) for fn in payload["filenames"]
        ]

    job_id = schedule_display_at(run_date, task_type, payload, job_id=data.get("job_id"))
    return jsonify({"status": "scheduled", "job_id": job_id, "run_at": run_date.isoformat()}), 201


@schedule_bp.route("/<job_id>", methods=["DELETE"])
def cancel_scheduled_job(job_id: str):
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        return jsonify({"status": "deleted", "job_id": job_id})
    return jsonify({"error": "Job ID not found"}), 404