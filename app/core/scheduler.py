import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from app.core.matrix_engine import matrix_engine
from app.core.tasks import StaticImageTask, AnimationTask, PluginTask, ClearTask
from app.plugins import PLUGIN_REGISTRY

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def execute_scheduled_display(task_type: str, payload: dict) -> None:
    """
    Top-level callback executed by APScheduler when a timer fires.
    Reconstructs the DisplayTask from primitive serialized data and sends to MatrixEngine.
    """
    logger.info(f"Executing scheduled display: type={task_type}, payload={payload}")
    if task_type == "static":
        matrix_engine.set_task(StaticImageTask(payload["image_path"]))
    elif task_type == "animation":
        matrix_engine.set_task(
            AnimationTask(
                image_paths=payload["image_paths"],
                fps=payload.get("fps", 10.0),
                loop=payload.get("loop", True),
            )
        )
    elif task_type == "plugin":
        plugin_name = payload["plugin_name"]
        plugin_cls = PLUGIN_REGISTRY.get(plugin_name)
        if plugin_cls:
            matrix_engine.set_task(PluginTask(plugin_cls(), payload.get("params", {})))
        else:
            logger.error(f"Scheduled plugin '{plugin_name}' not found.")
    elif task_type == "clear":
        matrix_engine.set_task(ClearTask())


def init_scheduler(jobstore_uri: str) -> None:
    jobstores = {"default": SQLAlchemyJobStore(url=jobstore_uri)}
    scheduler.configure(jobstores=jobstores)
    scheduler.start()
    logger.info(f"Persistent scheduler started with store: {jobstore_uri}")


def schedule_display_at(run_date: datetime, task_type: str, payload: dict, job_id: str | None = None) -> str:
    job = scheduler.add_job(
        func=execute_scheduled_display,
        trigger="date",
        run_date=run_date,
        args=[task_type, payload],
        id=job_id,
        replace_existing=True,
    )
    return job.id