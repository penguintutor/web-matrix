import os
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from app.core.scheduler import (
    scheduler,
    schedule_one_off,
    schedule_annual,
    schedule_daily,
)

schedule_bp = Blueprint("schedule", __name__, url_prefix="/api/schedule")


@schedule_bp.route("/", methods=["GET"])
def list_scheduled_jobs():
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": (
                    job.next_run_time.isoformat() if job.next_run_time else None
                ),
                "task_type": job.args[0] if job.args else None,
                "payload": job.args[1] if len(job.args) > 1 else None,
            }
        )
    return jsonify({"scheduled_jobs": jobs})


@schedule_bp.route("/add", methods=["POST"])
def add_scheduled_job():
    """
    Schedule a display task via JSON API.
    Supports recurrence: "annual", "daily", or "once" (default).
    """
    data = request.get_json(silent=True) or {}
    recurrence = data.get("recurrence", "once")
    task_type = data.get("task_type")
    payload = data.get("payload", {})
    job_id = data.get("job_id")

    if task_type not in ("static", "sequence", "plugin", "clear"):
        return jsonify({"error": "Invalid 'task_type'"}), 400

    # Normalize static image path to IMAGES_FOLDER
    if task_type == "static" and "filename" in payload:
        safe_fn = secure_filename(payload["filename"])
        payload["filename"] = safe_fn
        payload["image_path"] = os.path.join(
            current_app.config["IMAGES_FOLDER"], safe_fn
        )
    elif task_type == "sequence" and "sequence_name" in payload:
        payload["sequence_name"] = secure_filename(payload["sequence_name"])

    try:
        if recurrence == "annual":
            month = int(data["month"])
            day = int(data["day"])
            hour = int(data.get("hour", 9))
            minute = int(data.get("minute", 0))
            created_id = schedule_annual(
                month, day, hour, minute, task_type, payload, job_id=job_id
            )
        elif recurrence == "daily":
            hour = int(data["hour"])
            minute = int(data.get("minute", 0))
            created_id = schedule_daily(
                hour, minute, task_type, payload, job_id=job_id
            )
        else:
            run_date = datetime.fromisoformat(data["run_at"])
            created_id = schedule_one_off(
                run_date, task_type, payload, job_id=job_id
            )
    except (KeyError, ValueError, TypeError) as exc:
        return jsonify({"error": f"Invalid schedule parameters: {exc}"}), 400

    return jsonify(
        {
            "status": "scheduled",
            "recurrence": recurrence,
            "job_id": created_id,
        }
    ), 201


@schedule_bp.route("/<job_id>", methods=["DELETE"])
def cancel_scheduled_job(job_id: str):
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        return jsonify({"status": "deleted", "job_id": job_id})
    return jsonify({"error": "Job ID not found"}), 404