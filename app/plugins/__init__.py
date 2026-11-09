# app/plugins/__init__.py
import importlib
import pkgutil
import inspect
from app.plugins.base import BasePlugin

PLUGIN_REGISTRY: dict[str, type[BasePlugin]] = {}

def discover_plugins() -> dict[str, type[BasePlugin]]:
    """Dynamically loads all BasePlugin subclasses in the app.plugins package."""
    PLUGIN_REGISTRY.clear()
    package = __name__
    for _, module_name, _ in pkgutil.iter_modules(__path__):
        if module_name == "base":
            continue
        module = importlib.import_module(f"{package}.{module_name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                PLUGIN_REGISTRY[obj.name] = obj
    return PLUGIN_REGISTRY