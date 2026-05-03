import logging
import os
import shutil

import config

logger = logging.getLogger(__name__)


def log_debug(message):
    logger.info(message)


def prepare_task_work_dir(task_id):
    task_dir = os.path.join(config.WORK_DIR, task_id)
    if os.path.exists(task_dir):
        shutil.rmtree(task_dir, ignore_errors=True)
    os.makedirs(task_dir, exist_ok=True)
    return task_dir


def move_to_library(src_path, dest_name):
    if not src_path or not os.path.exists(src_path):
        return None
    if os.path.isfile(src_path) and os.path.getsize(src_path) <= 0:
        log_debug(f"Refusing to move empty artifact into library: {src_path}")
        return None

    dest_path = os.path.join(config.DOWNLOADS_DIR, dest_name)
    if os.path.exists(dest_path):
        if os.path.isdir(dest_path):
            shutil.rmtree(dest_path)
        else:
            os.remove(dest_path)
    return shutil.move(src_path, dest_path)
