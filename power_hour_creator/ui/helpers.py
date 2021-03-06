import os

from PyQt5.QtWidgets import QFileDialog

from power_hour_creator import config


def identity(x):
    return x


def store_results_in_settings(
        key,
        settings=config.get_persistent_settings(),
        transform=identity):
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            settings.setValue(key, transform(result))
            return result
        return wrapper
    return decorator


def store_dirname_in_settings(key, settings=config.get_persistent_settings()):
    def dirname_if_path_or_old_value(path):
        folder = os.path.dirname(path)

        if folder:
            return folder
        else:
            return settings.value(key)

    return store_results_in_settings(
        key=key, settings=settings, transform=dirname_if_path_or_old_value)


def get_save_file_name(parent, caption, directory, filter, ext):
    path, _ = QFileDialog.getSaveFileName(parent, caption, directory, filter)

    if path and not path.endswith(ext):
        return path + ext
    else:
        return path