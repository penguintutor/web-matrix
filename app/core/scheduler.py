import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from app.core.matrix_engine import matrix_engine
from app.core.tasks import StaticImageTask, PluginTask, ClearTask
from app.core.sequences import sequence_manager
from app.plugins import PLUGIN_REGISTRY

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

MONTH_NAMES = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]


def execute_scheduled_display(task_type: str, payload: dict) -> None:
    """
    Top-level callback executed by APScheduler when a timer fires.
    Reconstructs the DisplayTask and hands it to MatrixEngine.
    """
    logger.info(f"Executing scheduled display: type={task_type}, payload={payload}")
    if task_type == "static":
        matrix_engine.set_task(
            StaticImageTask(payload["image_path"]),
            label=payload.get("filename", "Image"),
        )
    elif task_type == "sequence":
        seq_name = payload["sequence_name"]
        task = sequence_manager.build_task(seq_name)
        if task:
            matrix_engine.set_task(task, label=seq_name)
        else:
            logger.error(f"Scheduled sequence '{seq_name}' not found or empty.")
    elif task_type == "plugin":
        plugin_name = payload["plugin_name"]
        plugin_cls = PLUGIN_REGISTRY.get(plugin_name)
        if plugin_cls:
            params = payload.get("params", {})
            matrix_engine.set_task(
                PluginTask(plugin_cls(), params),
                label=params.get("text", plugin_name)[:16],
            )
        else:
            logger.error(f"Scheduled plugin '{plugin_name}' not found.")
    elif task_type == "clear":
        matrix_engine.set_task(ClearTask(), label="Cleared")


def init_scheduler(jobstore_uri: str) -> None:
    jobstores = {"default": SQLAlchemyJobStore(url=jobstore_uri)}
    # misfire_grace_time=3600 allows a job to still fire if the Pi was powered off
    # at the exact minute and booted up within an hour of the scheduled time.
    job_defaults = {"misfire_grace_time": 3600, "coalesce": True}
    scheduler.configure(jobstores=jobstores, job_defaults=job_defaults)
    scheduler.start()
    logger.info(f"Persistent scheduler started with store: {jobstore_uri}")


def schedule_one_off(
    run_date: datetime, task_type: str, payload: dict, job_id: str | None = None
) -> str:
    """Runs once on a specific YYYY-MM-DD HH:MM date and is then removed."""
    label = f"Once: {run_date.strftime('%Y-%m-%d %H:%M')}"
    job = scheduler.add_job(
        func=execute_scheduled_display,
        trigger="date",
        run_date=run_date,
        args=[task_type, payload],
        name=label,
        id=job_id,
        replace_existing=True,
    )
    return job.id


def schedule_annual(
    month: int,
    day: int,
    hour: int,
    minute: int,
    task_type: str,
    payload: dict,
    job_id: str | None = None,
) -> str:
    """Runs every year on the given month, day, hour, and minute."""
    label = f"Yearly: {day:02d} {MONTH_NAMES[month]} @ {hour:02d}:{minute:02d}"
    job = scheduler.add_job(
        func=execute_scheduled_display,
        trigger="cron",
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        args=[task_type, payload],
        name=label,
        id=job_id,
        replace_existing=True,
    )
    return job.id


def schedule_daily(
    hour: int,
    minute: int,
    task_type: str,
    payload: dict,
    job_id: str | None = None,
) -> str:
    """Runs every day at the given hour and minute (useful for nighttime clear)."""
    label = f"Daily @ {hour:02d}:{minute:02d}"
    job = scheduler.add_job(
        func=execute_scheduled_display,
        trigger="cron",
        hour=hour,
        minute=minute,
        args=[task_type, payload],
        name=label,
        id=job_id,
        replace_existing=True,
    )
    return job.id