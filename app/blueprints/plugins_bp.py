from flask import Blueprint, request, jsonify
from app.plugins import PLUGIN_REGISTRY
from app.core.matrix_engine import matrix_engine
from app.core.tasks import PluginTask

plugins_bp = Blueprint("plugins", __name__, url_prefix="/api/plugins")


@plugins_bp.route("/", methods=["GET"])
def list_plugins():
    plugins_info = [
        {"name": name, "description": cls.description}
        for name, cls in PLUGIN_REGISTRY.items()
    ]
    return jsonify({"plugins": plugins_info})


@plugins_bp.route("/<plugin_name>/run", methods=["POST"])
def run_plugin(plugin_name: str):
    plugin_cls = PLUGIN_REGISTRY.get(plugin_name)
    if not plugin_cls:
        return jsonify({"error": f"Plugin '{plugin_name}' not found"}), 404

    params = request.get_json(silent=True) or {}
    matrix_engine.set_task(PluginTask(plugin_cls(), params))
    return jsonify({"status": "running_plugin", "plugin": plugin_name, "params": params})