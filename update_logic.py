import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

# ============================================================
# ОСНОВНЫЕ ПУТИ
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# Гарантируем, что Python видит файлы самого Mace Launcher
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

VERSION_FILE = BASE_DIR / "version.json"

UPDATE_ROOT_DIR = BASE_DIR / "updates"
LEGACY_UPDATE_DIR = BASE_DIR / "update"

UPDATE_PACKAGE_DIR = UPDATE_ROOT_DIR / "MaceUpdate"
UPDATE_DIR_CANDIDATES = [
    UPDATE_PACKAGE_DIR,
    LEGACY_UPDATE_DIR
]

OLD_FILES_DIR = BASE_DIR / "old_files"


# ============================================================
# ВСТРОЕННЫЙ PYTHON
# ============================================================

def get_python_executable():
    """
    Возвращает абсолютный путь к python/python.exe в папке проекта.
    """
    embedded_python = BASE_DIR / "python" / "python.exe"
    if embedded_python.exists():
        return str(embedded_python)

    if not getattr(sys, "frozen", False):
        python_exe = Path(sys.executable)
        if python_exe.exists():
            return str(python_exe)

    system_python = shutil.which("python")
    if system_python:
        return system_python

    return "python"


PYTHON_EXE = get_python_executable()


# ============================================================
# ОБНОВЛЕНИЯ
# ============================================================

def get_update_dir():
    for folder in UPDATE_DIR_CANDIDATES:
        if folder.exists():
            return folder

    UPDATE_ROOT_DIR.mkdir(parents=True, exist_ok=True)
    UPDATE_PACKAGE_DIR.mkdir(parents=True, exist_ok=True)

    return UPDATE_PACKAGE_DIR


def prune_updates_root():
    if not UPDATE_ROOT_DIR.exists():
        return

    for item in sorted(UPDATE_ROOT_DIR.iterdir()):
        if item.name == "update":
            continue

        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
        except Exception:
            pass


# ============================================================
# ВЕРСИЯ
# ============================================================

def read_current_version():
    try:
        if VERSION_FILE.exists():
            data = json.loads(
                VERSION_FILE.read_text(encoding="utf-8")
            )

            if isinstance(data, dict):
                version = (
                    data.get("version")
                    or data.get("app_version")
                    or "0.0.0"
                )

                return str(version)

    except Exception:
        pass

    return "0.0.0"


def version_to_tuple(version_text):
    parts = re.findall(r"\d+", str(version_text))

    if not parts:
        return (0, 0, 0)

    return tuple(
        int(part)
        for part in parts[:3]
    )


def is_version_newer(candidate, current):
    return (
        version_to_tuple(candidate)
        >
        version_to_tuple(current)
    )


# ============================================================
# MANIFEST
# ============================================================

def read_manifest(update_dir):
    manifest_path = update_dir / "manifest.json"

    if not manifest_path.exists():
        return {}

    try:
        with open(
            manifest_path,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    return {}


# ============================================================
# ПОИСК АРХИВОВ
# ============================================================

def find_update_archives(update_dir):
    if not update_dir.exists():
        return []

    files = []

    for item in sorted(update_dir.iterdir()):
        if (
            item.is_file()
            and item.suffix.lower() in {".bin", ".zip"}
        ):
            files.append(item)

    return files


# ============================================================
# ЗАПУСК GUI
# ============================================================

def launch_gui():
    gui_script = BASE_DIR / "gui.py"

    if not gui_script.exists():
        print("Ошибка: gui.py не найден!")
        print(f"Ожидался файл: {gui_script}")
        return

    try:
        # Передаем текущие переменные окружения и добавляем BASE_DIR в PYTHONPATH,
        # чтобы Python во встроенной папке без проблем находил все локальные модули (language_loader и др.)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(BASE_DIR)

        subprocess.Popen(
            [
                PYTHON_EXE,
                str(gui_script)
            ],
            cwd=str(BASE_DIR),
            env=env
        )
        print("GUI успешно запущен!")

    except Exception as exc:
        print(f"Ошибка запуска GUI: {exc}")


# ============================================================
# BACKUP
# ============================================================

def backup_existing_file(dest: Path):
    if not dest.exists():
        return

    try:
        rel_path = dest.relative_to(BASE_DIR)
    except ValueError:
        return

    backup_path = OLD_FILES_DIR / rel_path
    backup_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    try:

        if dest.is_dir():

            if backup_path.exists():
                shutil.rmtree(
                    backup_path,
                    ignore_errors=True
                )

            shutil.copytree(
                dest,
                backup_path
            )

            shutil.rmtree(
                dest,
                ignore_errors=True
            )

        else:

            if backup_path.exists():
                backup_path.unlink()

            shutil.copy2(
                dest,
                backup_path
            )

            dest.unlink()

    except Exception as exc:
        print(
            f"Не удалось создать backup "
            f"{dest}: {exc}"
        )


# ============================================================
# УСТАНОВКА MATERIAL
# ============================================================

def install_material_update(material_dir: Path):

    if not material_dir.exists():
        return False, "Папка material не найдена"

    OLD_FILES_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    for item in sorted(material_dir.rglob("*")):

        if item.is_dir():
            continue

        rel_path = item.relative_to(
            material_dir
        )

        dst = BASE_DIR / rel_path

        dst.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if dst.exists():
            backup_existing_file(dst)

        shutil.copy2(
            item,
            dst
        )

    return True, "OK"


# ============================================================
# РАСПАКОВКА ОБНОВЛЕНИЯ
# ============================================================

def extract_update_archive(archive_path: Path):

    temp_dir = Path(
        tempfile.mkdtemp(
            prefix="mace_update_",
            dir=str(BASE_DIR)
        )
    )

    with zipfile.ZipFile(
        archive_path,
        "r"
    ) as archive:

        archive.extractall(
            temp_dir
        )

    return temp_dir


# ============================================================
# УСТАНОВКА АРХИВА
# ============================================================

def install_archive_update(archive_path: Path):

    if not archive_path.exists():
        return False, "Файл обновления не найден"

    temp_dir = extract_update_archive(
        archive_path
    )

    try:

        manifest = read_manifest(
            temp_dir
        )

        is_update = bool(
            manifest.get(
                "is_update",
                False
            )
        )

        version = str(
            manifest.get("version")
            or manifest.get("new_version")
            or "0.0.0"
        )

        if not is_update:
            return False, "is_update = false"

        if not is_version_newer(
            version,
            read_current_version()
        ):
            return (
                False,
                f"Версия обновления {version} "
                f"не больше текущей версии"
            )

        material_dir = temp_dir / "material"

        if material_dir.exists():
            return install_material_update(
                material_dir
            )

        # Если material нет,
        # устанавливаем файлы напрямую

        for item in sorted(
            temp_dir.rglob("*")
        ):

            if item.is_dir():
                continue

            if item.name == "manifest.json":
                continue

            rel_path = item.relative_to(
                temp_dir
            )

            dst = BASE_DIR / rel_path

            if dst.exists():
                backup_existing_file(dst)

            dst.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            shutil.copy2(
                item,
                dst
            )

        return True, "OK"

    finally:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )


# ============================================================
# ОЧИСТКА ОБНОВЛЕНИЙ
# ============================================================

def cleanup_update_dirs():

    prune_updates_root()

    if LEGACY_UPDATE_DIR.exists():
        shutil.rmtree(
            LEGACY_UPDATE_DIR,
            ignore_errors=True
        )

    if UPDATE_PACKAGE_DIR.exists():
        shutil.rmtree(
            UPDATE_PACKAGE_DIR,
            ignore_errors=True
        )

    UPDATE_ROOT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # На всякий случай ещё раз устанавливаем
    # правильную рабочую директорию

    try:
        os.chdir(BASE_DIR)
    except Exception:
        pass

    update_dir = get_update_dir()

    update_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    prune_updates_root()

    material_dir = update_dir / "material"

    manifest = read_manifest(
        update_dir
    )

    archive_files = find_update_archives(
        update_dir
    )

    try:

        # ----------------------------------------------------
        # MATERIAL UPDATE
        # ----------------------------------------------------

        if material_dir.exists():

            ok, msg = install_material_update(
                material_dir
            )

            if ok:
                cleanup_update_dirs()
            else:
                print(
                    f"Ошибка обновления "
                    f"через material: {msg}"
                )

        # ----------------------------------------------------
        # ARCHIVE UPDATE
        # ----------------------------------------------------

        elif archive_files:

            selected_archive = archive_files[0]

            ok, msg = install_archive_update(
                selected_archive
            )

            if ok:
                cleanup_update_dirs()
            else:
                print(
                    f"Ошибка обновления "
                    f"через архив: {msg}"
                )

        # ----------------------------------------------------
        # MANIFEST WITHOUT MATERIAL
        # ----------------------------------------------------

        elif manifest.get("is_update"):

            manifest_version = str(
                manifest.get("version")
                or manifest.get("new_version")
                or "0.0.0"
            )

            if not is_version_newer(
                manifest_version,
                read_current_version()
            ):

                print(
                    "Обновление не применено: "
                    "версия не актуальнее текущей"
                )

            else:

                print(
                    "Найдена метаинформация "
                    "обновления, но материал "
                    "не найден"
                )

    except Exception as exc:

        print(
            f"Ошибка установки обновления: {exc}"
        )

    finally:

        # GUI запускается ВСЕГДА,
        # даже если обновление сломалось

        launch_gui()


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    main()