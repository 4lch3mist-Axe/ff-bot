import importlib
import pkgutil
import asyncio
from core.logger import log, module_log
from config import MODULES_CONFIG


def load_modules(tree, guild_id, base_package="modules"):
    log("Module loader started", "BOOT")

    package = importlib.import_module(base_package)

    for module_info in pkgutil.iter_modules(package.__path__):
        module_name = module_info.name

        # 🔐 Feature flag
        enabled = MODULES_CONFIG.get(module_name, True)

        if not enabled:
            module_log(module_name, "module disabled via config", "BOOT")
            continue

        commands_path = f"{base_package}.{module_name}.commands"

        try:
            module = importlib.import_module(commands_path)

            if hasattr(module, "setup"):
                module.setup(tree, guild_id)
                module_log(module_name, "module loaded", "BOOT")
            else:
                module_log(module_name, "no setup() found", "WARN")

        except ModuleNotFoundError:
            module_log(module_name, "no commands.py found", "WARN")

        except Exception as e:
            module_log(module_name, f"failed to load: {e}", "ERROR")
            raise

async def load_module_jobs(bot, base_package="modules"):
    from config import MODULES_CONFIG
    from core.logger import module_log

    package = importlib.import_module(base_package)

    for module_info in pkgutil.iter_modules(package.__path__):
        module_name = module_info.name

        if not MODULES_CONFIG.get(module_name, True):
            continue

        jobs_path = f"{base_package}.{module_name}.jobs"

        try:
            jobs_module = importlib.import_module(jobs_path)

            if hasattr(jobs_module, "setup"):
                module_log(module_name, "starting jobs", "BOOT")
                await jobs_module.setup(bot)
            else:
                module_log(module_name, "no jobs.setup()", "WARN")

        except ModuleNotFoundError:
            # jobs.py optionnel → silence volontaire
            pass

        except Exception as e:
            module_log(module_name, f"jobs failed: {e}", "ERROR")
            raise