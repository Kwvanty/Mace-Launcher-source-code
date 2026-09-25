import os
import sys
import re
import shutil
import subprocess
import uuid
import json
import threading
import traceback
import urllib.request
import minecraft_launcher_lib

fabric_loader = forge_loader = neoforge_loader = curseforge_loader = None

try:
    from loaders import fabric_loader as fabric_loader
except ImportError:
    try:
        from loaders import fabric as fabric_loader
    except ImportError:
        fabric_loader = None

try:
    from loaders import forge as forge_loader
except ImportError:
    try:
        from loaders import forge_loader as forge_loader
    except ImportError:
        forge_loader = None

try:
    from loaders import neoforge as neoforge_loader
except ImportError:
    try:
        from loaders import neoforge as neoforge_loader
    except ImportError:
        neoforge_loader = None

try:
    from loaders import curseforge as curseforge_loader
except ImportError:
    try:
        from loaders import curseforge_loader as curseforge_loader
    except ImportError:
        curseforge_loader = None

MINECRAFT_DIR = minecraft_launcher_lib.utils.get_minecraft_directory()
VBACKUPS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "vBackups"
)

game_process = None
game_process_user_stopped = False


# ============================================================
# MACE LAUNCHER VERSION
# ============================================================

def get_launcher_version():
    version_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Version.json"
    )

    try:
        with open(version_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return str(data.get("version", "1.0.6"))

    except Exception:
        return "1.0.6"


# ============================================================
# JAVA
# ============================================================

def get_required_java_version(mc_version="1.21"):
    """
    Возвращает требуемую major-версию Java для Minecraft.
    """

    version = str(mc_version or "").strip()

    new_format = re.fullmatch(
        r"(\d+)(?:\.(\d+))?(?:\.(\d+))?",
        version
    )

    if new_format:
        first = int(new_format.group(1))

        if first >= 26:
            return 25

    match = re.fullmatch(
        r"1\.(\d+)(?:\.(\d+))?",
        version
    )

    if not match:
        return 21

    minor = int(match.group(1))
    patch = int(match.group(2) or 0)

    if minor <= 16:
        return 8

    if minor == 17:
        return 16

    if 18 <= minor <= 20:
        if minor == 20 and patch >= 5:
            return 21

        return 17

    if minor == 21 and patch >= 11:
        return 25

    return 21


def _extract_java_major(version_output):
    """
    Корректно определяет Java major version.
    """

    if not version_output:
        return None

    match = re.search(
        r'version\s+"([^"]+)"',
        version_output
    )

    if not match:
        match = re.search(
            r'openjdk\s+(\d+)',
            version_output,
            re.IGNORECASE
        )

        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None

        return None

    version_string = match.group(1).strip()

    if version_string.startswith("1."):
        legacy_match = re.match(
            r"1\.(\d+)",
            version_string
        )

        if legacy_match:
            try:
                return int(legacy_match.group(1))
            except Exception:
                return None

    modern_match = re.match(
        r"(\d+)",
        version_string
    )

    if modern_match:
        try:
            return int(modern_match.group(1))
        except Exception:
            return None

    return None


def _check_java(java_path):
    """
    Проверяет Java и возвращает её major version.
    """

    try:
        result = subprocess.run(
            [java_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
            check=False
        )

        output = result.stdout or ""
        major = _extract_java_major(output)

        return major, output

    except Exception:
        return None, ""


def _add_java_candidates_from_directory(directory, candidates):
    """
    Рекурсивно ищет java.exe в директории.
    """

    if not directory or not os.path.isdir(directory):
        return

    try:
        for root, dirs, files in os.walk(directory):
            dirs[:] = [
                d for d in dirs
                if d.lower() not in (
                    "temp",
                    "cache",
                    "logs",
                    "__pycache__"
                )
            ]

            if "java.exe" in files:
                candidates.append(
                    os.path.join(root, "java.exe")
                )

    except Exception:
        pass


def find_suitable_java(mc_version="1.21"):
    """
    Находит Java, подходящую для конкретной версии Minecraft.
    """

    target_major = get_required_java_version(mc_version)

    appdata = os.getenv("APPDATA", "")
    program_files = os.getenv(
        "ProgramFiles",
        r"C:\Program Files"
    )
    program_files_x86 = os.getenv(
        "ProgramFiles(x86)",
        r"C:\Program Files (x86)"
    )
    local_appdata = os.getenv("LOCALAPPDATA", "")

    candidates = []

    def add(path):
        if path and path not in candidates:
            candidates.append(path)

    # JAVA_HOME
    java_home = os.getenv("JAVA_HOME")

    if java_home:
        add(
            os.path.join(
                java_home,
                "bin",
                "java.exe"
            )
        )

    # Стандартные директории
    java_roots = [
        os.path.join(program_files, "Java"),
        os.path.join(program_files, "Eclipse Adoptium"),
        os.path.join(program_files, "Microsoft"),
        os.path.join(program_files, "BellSoft"),
        os.path.join(program_files, "Amazon Corretto"),
        os.path.join(program_files, "Zulu"),
        os.path.join(program_files_x86, "Java"),
        os.path.join(
            local_appdata,
            "Programs",
            "Eclipse Adoptium"
        ),
    ]

    for root in java_roots:
        if os.path.isdir(root):
            try:
                for name in os.listdir(root):
                    full = os.path.join(root, name)

                    if os.path.isdir(full):
                        add(
                            os.path.join(
                                full,
                                "bin",
                                "java.exe"
                            )
                        )

            except Exception:
                pass

    # Известные стандартные пути
    for major in (8, 16, 17, 21, 25):
        known_paths = [
            rf"C:\Program Files\Eclipse Adoptium\jdk-{major}\bin\java.exe",
            rf"C:\Program Files\Eclipse Adoptium\jdk-{major}.0.2.13-hotspot\bin\java.exe",
            rf"C:\Program Files\Java\jdk-{major}\bin\java.exe",
            rf"C:\Program Files\Microsoft\jdk-{major}\bin\java.exe",
            rf"C:\Program Files\Microsoft\jdk-{major}.0.0\bin\java.exe",
        ]

        for path in known_paths:
            add(path)

    # Minecraft runtime
    mc_runtime = os.path.join(
        MINECRAFT_DIR,
        "runtime"
    )

    _add_java_candidates_from_directory(
        mc_runtime,
        candidates
    )

    # TLauncher
    tlauncher_jvms = os.path.join(
        appdata,
        ".tlauncher",
        "jvms"
    )

    _add_java_candidates_from_directory(
        tlauncher_jvms,
        candidates
    )

    # Runtime рядом с Mace Launcher
    mace_root = os.path.dirname(
        os.path.abspath(__file__)
    )

    local_runtime_dirs = [
        os.path.join(mace_root, "runtime"),
        os.path.join(mace_root, "java"),
        os.path.join(mace_root, "jre"),
        os.path.join(mace_root, "jdk"),
        os.path.join(
            mace_root,
            "python",
            "runtime"
        ),
    ]

    for directory in local_runtime_dirs:
        _add_java_candidates_from_directory(
            directory,
            candidates
        )

    # PATH
    add("java")

    exact_match = None
    newer_match = None
    fallback_match = None
    checked = set()

    for java_path in candidates:
        if java_path in checked:
            continue

        checked.add(java_path)

        major, output = _check_java(java_path)

        if major is None:
            continue

        if major == target_major:
            exact_match = java_path
            break

        if major > target_major and newer_match is None:
            newer_match = java_path

        if fallback_match is None:
            fallback_match = java_path

    if exact_match:
        return exact_match

    if newer_match:
        return newer_match

    if fallback_match:
        return fallback_match

    return "java"


def get_java_info(mc_version="1.21"):
    """
    Возвращает информацию о Java для логов.
    """

    required = get_required_java_version(mc_version)
    java_path = find_suitable_java(mc_version)
    actual, output = _check_java(java_path)

    return {
        "required": required,
        "path": java_path,
        "actual": actual,
        "output": output
    }


# ============================================================
# VERSIONS
# ============================================================

def get_installed_versions():
    versions_dir = os.path.join(
        MINECRAFT_DIR,
        "versions"
    )

    if not os.path.exists(versions_dir):
        return []

    installed = []

    for folder in os.listdir(versions_dir):
        json_path = os.path.join(
            versions_dir,
            folder,
            f"{folder}.json"
        )

        if os.path.exists(json_path):
            installed.append(folder)

    return sorted(installed)


def get_available_minecraft_versions():
    manifest_url = (
        "https://piston-meta.mojang.com/"
        "mc/game/version_manifest_v2.json"
    )

    try:
        req = urllib.request.Request(
            manifest_url,
            headers={
                "User-Agent": "MaceLauncher/1.0.5"
            }
        )

        with urllib.request.urlopen(
            req,
            timeout=10
        ) as response:
            data = json.loads(
                response.read().decode("utf-8")
            )

        return [
            item.get("id")
            for item in data.get("versions", [])
            if item.get("type") == "release"
            and item.get("id")
        ]

    except Exception:
        return get_installed_versions()


def _read_version_json(version_id):
    path = os.path.join(
        MINECRAFT_DIR,
        "versions",
        version_id,
        f"{version_id}.json"
    )

    if not os.path.exists(path):
        return None

    try:
        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    except Exception:
        return None


def _detect_loader(version_id):
    data = _read_version_json(version_id) or {}

    blob = json.dumps(
        data,
        ensure_ascii=False
    ).lower()

    if (
        "neoforge" in blob
        or "neoforged" in blob
    ):
        return "neoforge"

    if (
        "fabric-loader" in blob
        or "fabricloader" in blob
        or "net.fabricmc" in blob
    ):
        return "fabric"

    if (
        "forge" in blob
        or "cpw.mods" in blob
        or "modlauncher" in blob
    ):
        return "forge"

    if "curseforge" in blob:
        return "curseforge"

    return "vanilla"


def _get_mc_version_from_json(version_id):
    data = _read_version_json(version_id) or {}

    for key in (
        "inheritsFrom",
        "jar",
        "clientVersion",
        "minecraftVersion"
    ):
        value = data.get(key)

        if (
            isinstance(value, str)
            and re.fullmatch(
                r"\d+\.\d+(?:\.\d+)?",
                value.strip()
            )
        ):
            return value.strip()

    version_id_match = re.search(
        r"(?<!\d)1\.\d+(?:\.\d+)?(?!\d)",
        str(version_id or "")
    )

    if version_id_match:
        candidate = version_id_match.group(0)

        parts = [
            int(part)
            for part in candidate.split(".")
            if part.isdigit()
        ]

        if (
            len(parts) >= 2
            and parts[1] < 100
            and (
                len(parts) == 2
                or parts[2] < 100
            )
        ):
            return candidate

    new_version_match = re.search(
        r"(?<!\d)(2[6-9]|[3-9]\d)"
        r"(?:\.\d+){0,2}(?!\d)",
        str(version_id or "")
    )

    if new_version_match:
        return new_version_match.group(0)

    blob = json.dumps(
        data,
        ensure_ascii=False
    )

    for match in re.finditer(
        r"(?<!\d)1\.\d+(?:\.\d+)?(?!\d)",
        blob
    ):
        candidate = match.group(0)

        parts = [
            int(part)
            for part in candidate.split(".")
            if part.isdigit()
        ]

        if (
            len(parts) >= 2
            and parts[1] < 100
            and (
                len(parts) == 2
                or parts[2] < 100
            )
        ):
            return candidate

    for match in re.finditer(
        r"(?<!\d)(2[6-9]|[3-9]\d)"
        r"(?:\.\d+){0,2}(?!\d)",
        blob
    ):
        return match.group(0)

    return None


# ============================================================
# FILE OPERATIONS
# ============================================================

def _copy_directory_contents(
    src,
    dst,
    excluded_names=None
):
    excluded_names = set(
        excluded_names or []
    )

    os.makedirs(
        dst,
        exist_ok=True
    )

    for name in os.listdir(src):
        if name in excluded_names:
            continue

        source_path = os.path.join(
            src,
            name
        )

        target_path = os.path.join(
            dst,
            name
        )

        if os.path.isdir(source_path):
            if os.path.exists(target_path):
                shutil.rmtree(
                    target_path,
                    ignore_errors=True
                )

            shutil.copytree(
                source_path,
                target_path
            )

        else:
            shutil.copy2(
                source_path,
                target_path
            )


def ensure_version_json_valid(version_id):
    version_dir = os.path.join(
        MINECRAFT_DIR,
        "versions",
        version_id
    )

    json_path = os.path.join(
        version_dir,
        f"{version_id}.json"
    )

    if not os.path.exists(json_path):
        return False

    try:
        with open(
            json_path,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        if not data.get("id"):
            data["id"] = version_id

        with open(
            json_path,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                data,
                f,
                indent=4
            )

        return True

    except Exception:
        return False


# ============================================================
# UPDATE VERSION
# ============================================================

def update_version(
    version_name,
    target_mc_version
):
    if not version_name:
        return False, "Версія не вибрана."

    if not target_mc_version:
        return False, "Цільова версія Minecraft не вибрана."

    version_folder = os.path.join(
        MINECRAFT_DIR,
        "versions",
        version_name
    )

    if not os.path.isdir(version_folder):
        return False, (
            f"Версія '{version_name}' не знайдена."
        )

    loader_type = _detect_loader(
        version_name
    )

    temp_name = (
        f"__mace_update_"
        f"{uuid.uuid4().hex[:10]}"
    )

    temp_folder = os.path.join(
        MINECRAFT_DIR,
        "versions",
        temp_name
    )

    preserved_dirs = {
        "mods",
        "resourcepacks",
        "shaderpacks",
        "config",
        "saves",
        "screenshots"
    }

    try:
        if loader_type == "fabric":
            if not fabric_loader:
                return False, (
                    "Не знайдено модуль Fabric loader."
                )

            success, msg = fabric_loader.install(
                temp_name,
                target_mc_version,
                MINECRAFT_DIR
            )

        elif loader_type == "forge":
            if not forge_loader:
                return False, (
                    "Не знайдено модуль Forge loader."
                )

            success, msg = forge_loader.install(
                temp_name,
                target_mc_version,
                MINECRAFT_DIR
            )

        elif loader_type == "neoforge":
            if not neoforge_loader:
                return False, (
                    "Не знайдено модуль NeoForge loader."
                )

            success, msg = neoforge_loader.install(
                temp_name,
                target_mc_version,
                MINECRAFT_DIR
            )

        elif loader_type == "curseforge":
            if not curseforge_loader:
                return False, (
                    "Не знайдено модуль CurseForge loader."
                )

            success, msg = curseforge_loader.install(
                temp_name,
                target_mc_version,
                MINECRAFT_DIR
            )

        else:
            minecraft_launcher_lib.install.install_minecraft_version(
                target_mc_version,
                MINECRAFT_DIR
            )

            os.makedirs(
                temp_folder,
                exist_ok=True
            )

            base_dir = os.path.join(
                MINECRAFT_DIR,
                "versions",
                target_mc_version
            )

            base_json = os.path.join(
                base_dir,
                f"{target_mc_version}.json"
            )

            base_jar = os.path.join(
                base_dir,
                f"{target_mc_version}.jar"
            )

            if os.path.exists(base_json):
                with open(
                    base_json,
                    "r",
                    encoding="utf-8"
                ) as f:
                    data = json.load(f)

                data["id"] = temp_name

                with open(
                    os.path.join(
                        temp_folder,
                        f"{temp_name}.json"
                    ),
                    "w",
                    encoding="utf-8"
                ) as f:
                    json.dump(
                        data,
                        f,
                        indent=4
                    )

            if os.path.exists(base_jar):
                shutil.copy2(
                    base_jar,
                    os.path.join(
                        temp_folder,
                        f"{temp_name}.jar"
                    )
                )

            success = True
            msg = (
                f"Ванільна версія "
                f"{target_mc_version} підготовлена."
            )

        if not success:
            return False, msg

        if not os.path.exists(temp_folder):
            return False, (
                "Loader не створив тимчасову версію."
            )

        for name in os.listdir(version_folder):
            if name in preserved_dirs:
                continue

            path = os.path.join(
                version_folder,
                name
            )

            try:
                if os.path.isdir(path):
                    shutil.rmtree(
                        path,
                        ignore_errors=True
                    )
                else:
                    os.remove(path)

            except Exception:
                pass

        _copy_directory_contents(
            temp_folder,
            version_folder,
            preserved_dirs
        )

        temp_json = os.path.join(
            version_folder,
            f"{temp_name}.json"
        )

        final_json = os.path.join(
            version_folder,
            f"{version_name}.json"
        )

        if os.path.exists(temp_json):
            with open(
                temp_json,
                "r",
                encoding="utf-8"
            ) as f:
                data = json.load(f)

            data["id"] = version_name

            with open(
                final_json,
                "w",
                encoding="utf-8"
            ) as f:
                json.dump(
                    data,
                    f,
                    indent=4
                )

            os.remove(temp_json)

        temp_jar = os.path.join(
            version_folder,
            f"{temp_name}.jar"
        )

        final_jar = os.path.join(
            version_folder,
            f"{version_name}.jar"
        )

        if os.path.exists(temp_jar):
            if os.path.exists(final_jar):
                os.remove(final_jar)

            os.rename(
                temp_jar,
                final_jar
            )

        return True, (
            f"Версія '{version_name}' "
            f"оновлена до Minecraft "
            f"{target_mc_version}. "
            f"Loader: {loader_type}."
        )

    except Exception as e:
        return False, (
            f"Помилка оновлення версії: {e}"
        )

    finally:
        if os.path.exists(temp_folder):
            shutil.rmtree(
                temp_folder,
                ignore_errors=True
            )


# ============================================================
# UPDATE CLIENT
# ============================================================

def update_client(version_name):
    if not version_name:
        return False, "Версія не вибрана."

    version_folder = os.path.join(
        MINECRAFT_DIR,
        "versions",
        version_name
    )

    data = _read_version_json(
        version_name
    )

    if not data:
        return False, (
            f"Не знайдено JSON версії "
            f"'{version_name}'."
        )

    target_mc_version = _get_mc_version_from_json(
        version_name
    )

    if not target_mc_version:
        return False, (
            "Не вдалося визначити "
            "версію Minecraft."
        )

    loader_type = _detect_loader(
        version_name
    )

    temp_name = (
        f"__mace_reset_"
        f"{uuid.uuid4().hex[:10]}"
    )

    temp_folder = os.path.join(
        MINECRAFT_DIR,
        "versions",
        temp_name
    )

    try:
        if loader_type == "fabric":
            if not fabric_loader:
                return False, (
                    "Не знайдено модуль Fabric loader."
                )

            success, msg = fabric_loader.install(
                temp_name,
                target_mc_version,
                MINECRAFT_DIR
            )

        elif loader_type == "forge":
            if not forge_loader:
                return False, (
                    "Не знайдено модуль Forge loader."
                )

            success, msg = forge_loader.install(
                temp_name,
                target_mc_version,
                MINECRAFT_DIR
            )

        elif loader_type == "neoforge":
            if not neoforge_loader:
                return False, (
                    "Не знайдено модуль NeoForge loader."
                )

            success, msg = neoforge_loader.install(
                temp_name,
                target_mc_version,
                MINECRAFT_DIR
            )

        elif loader_type == "curseforge":
            if not curseforge_loader:
                return False, (
                    "Не знайдено модуль CurseForge loader."
                )

            success, msg = curseforge_loader.install(
                temp_name,
                target_mc_version,
                MINECRAFT_DIR
            )

        else:
            minecraft_launcher_lib.install.install_minecraft_version(
                target_mc_version,
                MINECRAFT_DIR
            )

            os.makedirs(
                temp_folder,
                exist_ok=True
            )

            base_dir = os.path.join(
                MINECRAFT_DIR,
                "versions",
                target_mc_version
            )

            base_json = os.path.join(
                base_dir,
                f"{target_mc_version}.json"
            )

            base_jar = os.path.join(
                base_dir,
                f"{target_mc_version}.jar"
            )

            if os.path.exists(base_json):
                with open(
                    base_json,
                    "r",
                    encoding="utf-8"
                ) as f:
                    data = json.load(f)

                data["id"] = temp_name

                with open(
                    os.path.join(
                        temp_folder,
                        f"{temp_name}.json"
                    ),
                    "w",
                    encoding="utf-8"
                ) as f:
                    json.dump(
                        data,
                        f,
                        indent=4
                    )

            if os.path.exists(base_jar):
                shutil.copy2(
                    base_jar,
                    os.path.join(
                        temp_folder,
                        f"{temp_name}.jar"
                    )
                )

            success = True
            msg = (
                f"Ванільна версія "
                f"{target_mc_version} підготовлена."
            )

        if not success:
            return False, msg

        if not os.path.exists(temp_folder):
            return False, (
                "Loader не створив тимчасову версію."
            )

        if os.path.exists(version_folder):
            shutil.rmtree(
                version_folder,
                ignore_errors=True
            )

        os.makedirs(
            version_folder,
            exist_ok=True
        )

        _copy_directory_contents(
            temp_folder,
            version_folder
        )

        temp_json = os.path.join(
            version_folder,
            f"{temp_name}.json"
        )

        final_json = os.path.join(
            version_folder,
            f"{version_name}.json"
        )

        if os.path.exists(temp_json):
            with open(
                temp_json,
                "r",
                encoding="utf-8"
            ) as f:
                final_data = json.load(f)

            final_data["id"] = version_name

            with open(
                final_json,
                "w",
                encoding="utf-8"
            ) as f:
                json.dump(
                    final_data,
                    f,
                    indent=4
                )

            os.remove(temp_json)

        temp_jar = os.path.join(
            version_folder,
            f"{temp_name}.jar"
        )

        final_jar = os.path.join(
            version_folder,
            f"{version_name}.jar"
        )

        if os.path.exists(temp_jar):
            if os.path.exists(final_jar):
                os.remove(final_jar)

            os.rename(
                temp_jar,
                final_jar
            )

        for folder_name in (
            "mods",
            "resourcepacks",
            "shaderpacks",
            "config"
        ):
            os.makedirs(
                os.path.join(
                    version_folder,
                    folder_name
                ),
                exist_ok=True
            )

        return True, (
            f"Клієнт '{version_name}' "
            f"встановлено заново. "
            f"Minecraft {target_mc_version}, "
            f"loader: {loader_type}."
        )

    except Exception as e:
        return False, (
            f"Помилка повного скидання "
            f"клієнта: {e}"
        )

    finally:
        if os.path.exists(temp_folder):
            shutil.rmtree(
                temp_folder,
                ignore_errors=True
            )


# ============================================================
# JAR
# ============================================================

def update_jar(version_name):
    if not version_name:
        return False, "Версія не вибрана."

    version_folder = os.path.join(
        MINECRAFT_DIR,
        "versions",
        version_name
    )

    if not os.path.isdir(version_folder):
        return False, (
            f"Версія '{version_name}' не знайдена."
        )

    target_mc_version = _get_mc_version_from_json(
        version_name
    )

    if not target_mc_version:
        return False, (
            "Не вдалося визначити "
            "базову версію Minecraft."
        )

    try:
        minecraft_launcher_lib.install.install_minecraft_version(
            target_mc_version,
            MINECRAFT_DIR
        )

        source_jar = os.path.join(
            MINECRAFT_DIR,
            "versions",
            target_mc_version,
            f"{target_mc_version}.jar"
        )

        target_jar = os.path.join(
            version_folder,
            f"{version_name}.jar"
        )

        if not os.path.exists(source_jar):
            return False, (
                f"JAR Minecraft "
                f"{target_mc_version} не знайдено."
            )

        shutil.copy2(
            source_jar,
            target_jar
        )

        return True, (
            f"JAR версії "
            f"'{version_name}' оновлено."
        )

    except Exception as e:
        return False, (
            f"Помилка оновлення JAR: {e}"
        )


# ============================================================
# BACKUPS
# ============================================================

def backup_version(version_name):
    if not version_name:
        return False, "Версія не вибрана."

    source = os.path.join(
        MINECRAFT_DIR,
        "versions",
        version_name
    )

    if not os.path.isdir(source):
        return False, (
            f"Версія '{version_name}' не знайдена."
        )

    try:
        os.makedirs(
            VBACKUPS_DIR,
            exist_ok=True
        )

        destination = os.path.join(
            VBACKUPS_DIR,
            version_name
        )

        if os.path.exists(destination):
            shutil.rmtree(
                destination,
                ignore_errors=True
            )

        shutil.copytree(
            source,
            destination
        )

        return True, (
            f"Бэкап '{version_name}' створено."
        )

    except Exception as e:
        return False, (
            f"Помилка створення бэкапа: {e}"
        )


def list_version_backups():
    if not os.path.isdir(VBACKUPS_DIR):
        return []

    return sorted([
        name
        for name in os.listdir(VBACKUPS_DIR)
        if os.path.isdir(
            os.path.join(
                VBACKUPS_DIR,
                name
            )
        )
    ])


def restore_version_backup(version_name):
    if not version_name:
        return False, "Версія не вибрана."

    backup = os.path.join(
        VBACKUPS_DIR,
        version_name
    )

    target = os.path.join(
        MINECRAFT_DIR,
        "versions",
        version_name
    )

    if not os.path.isdir(backup):
        return False, (
            f"Бэкап для '{version_name}' не знайдено."
        )

    try:
        if os.path.exists(target):
            shutil.rmtree(
                target,
                ignore_errors=True
            )

        shutil.copytree(
            backup,
            target
        )

        return True, (
            f"Версія '{version_name}' відновлена."
        )

    except Exception as e:
        return False, (
            f"Помилка відновлення: {e}"
        )


# ============================================================
# DELETE
# ============================================================

def delete_modpack(version_name):
    if not version_name:
        return False, "Версія не вибрана."

    target = os.path.join(
        MINECRAFT_DIR,
        "versions",
        version_name
    )

    if not os.path.isdir(target):
        return False, (
            f"Версія '{version_name}' не знайдена."
        )

    try:
        shutil.rmtree(target)

        return True, (
            f"Мод-пак '{version_name}' видалено."
        )

    except Exception as e:
        return False, (
            f"Помилка видалення мод-пака: {e}"
        )


# ============================================================
# CREATE VERSION
# ============================================================

def create_new_version(
    version_name,
    mc_version,
    loader_type
):
    if not version_name:
        return False, (
            "Ім'я версії не може бути порожнім!"
        )

    if not mc_version:
        return False, (
            "Версія Minecraft не вибрана!"
        )

    version_folder = os.path.join(
        MINECRAFT_DIR,
        "versions",
        version_name
    )

    if os.path.exists(version_folder):
        return False, (
            f"ЗАХИСТ: Версія "
            f"'{version_name}' вже існує!"
        )

    try:
        loader_lower = str(
            loader_type
        ).lower().strip()

        if loader_lower == "fabric":
            if not fabric_loader:
                return False, (
                    "ПОМИЛКА: Модуль Fabric відсутній!"
                )

            success, msg = fabric_loader.install(
                version_name,
                mc_version,
                MINECRAFT_DIR
            )

        elif loader_lower == "forge":
            if not forge_loader:
                return False, (
                    "ПОМИЛКА: Модуль Forge відсутній!"
                )

            success, msg = forge_loader.install(
                version_name,
                mc_version,
                MINECRAFT_DIR
            )

        elif loader_lower == "neoforge":
            if not neoforge_loader:
                return False, (
                    "ПОМИЛКА: Модуль NeoForge відсутній!"
                )

            success, msg = neoforge_loader.install(
                version_name,
                mc_version,
                MINECRAFT_DIR
            )

        elif loader_lower == "curseforge":
            if not curseforge_loader:
                return False, (
                    "ПОМИЛКА: Модуль CurseForge відсутній!"
                )

            success, msg = curseforge_loader.install(
                version_name,
                mc_version,
                MINECRAFT_DIR
            )

        elif loader_lower in (
            "vanilla",
            "чиста"
        ):
            minecraft_launcher_lib.install.install_minecraft_version(
                mc_version,
                MINECRAFT_DIR
            )

            os.makedirs(
                version_folder,
                exist_ok=True
            )

            base_dir = os.path.join(
                MINECRAFT_DIR,
                "versions",
                mc_version
            )

            base_jar = os.path.join(
                base_dir,
                f"{mc_version}.jar"
            )

            target_jar = os.path.join(
                version_folder,
                f"{version_name}.jar"
            )

            if os.path.exists(base_jar):
                shutil.copy2(
                    base_jar,
                    target_jar
                )

            _copy_base_version_json(
                version_name,
                mc_version,
                "net.minecraft.client.main.Main"
            )

            success = True
            msg = (
                f"Ванільна версія "
                f"'{version_name}' створена."
            )

        else:
            return False, (
                f"Невідомий тип "
                f"завантажувача: "
                f"'{loader_type}'"
            )

        if not success:
            if os.path.exists(version_folder):
                shutil.rmtree(
                    version_folder,
                    ignore_errors=True
                )

            return False, msg

        for folder_name in (
            "mods",
            "resourcepacks",
            "shaderpacks",
            "config"
        ):
            os.makedirs(
                os.path.join(
                    version_folder,
                    folder_name
                ),
                exist_ok=True
            )

        return True, msg

    except Exception as e:
        if os.path.exists(version_folder):
            shutil.rmtree(
                version_folder,
                ignore_errors=True
            )

        return False, (
            f"Помилка створення збірки: {e}"
        )


def _copy_base_version_json(
    version_name,
    base_version,
    main_class=None
):
    base_json_path = os.path.join(
        MINECRAFT_DIR,
        "versions",
        base_version,
        f"{base_version}.json"
    )

    target_dir = os.path.join(
        MINECRAFT_DIR,
        "versions",
        version_name
    )

    os.makedirs(
        target_dir,
        exist_ok=True
    )

    target_json_path = os.path.join(
        target_dir,
        f"{version_name}.json"
    )

    if not os.path.exists(base_json_path):
        try:
            minecraft_launcher_lib.install.install_minecraft_version(
                base_version,
                MINECRAFT_DIR
            )
        except Exception:
            pass

    if os.path.exists(base_json_path):
        with open(
            base_json_path,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        data["id"] = version_name

        if main_class:
            data["mainClass"] = main_class

        with open(
            target_json_path,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                data,
                f,
                indent=4
            )

    else:
        data = {
            "id": version_name,
            "inheritsFrom": base_version,
            "mainClass": (
                main_class
                or "net.minecraft.client.main.Main"
            ),
            "type": "release",
            "assets": base_version
        }

        with open(
            target_json_path,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                data,
                f,
                indent=4
            )


# ============================================================
# PROCESS
# ============================================================

def read_process_output(
    pipe,
    log_func
):
    try:
        for line in iter(
            pipe.readline,
            ""
        ):
            if line:
                log_func(
                    line.rstrip()
                )
            else:
                break

    except Exception:
        pass

    finally:
        try:
            pipe.close()
        except Exception:
            pass


# ============================================================
# START MINECRAFT
# ============================================================

def start_minecraft(
    username,
    version_id,
    ram_gb=4,
    log_func=print
):
    global game_process, game_process_user_stopped
    game_process_user_stopped = False

    try:
        log_func(
            f"[Mace Launcher] "
            f"Запуск збірки: "
            f"{version_id}..."
        )

        version_folder = os.path.join(
            MINECRAFT_DIR,
            "versions",
            version_id
        )

        json_path = os.path.join(
            version_folder,
            f"{version_id}.json"
        )

        if not os.path.exists(json_path):
            raise FileNotFoundError(
                f"JSON версії не знайдено: "
                f"{json_path}"
            )

        for folder in (
            "mods",
            "resourcepacks",
            "shaderpacks",
            "config"
        ):
            os.makedirs(
                os.path.join(
                    version_folder,
                    folder
                ),
                exist_ok=True
            )

        with open(
            json_path,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        data = _normalize_launcher_json_arguments(
            data
        )

        with open(
            json_path,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False
            )

        mc_version = _get_mc_version_from_json(
            version_id
        )

        if not mc_version:
            raise RuntimeError(
                f"Не вдалося визначити "
                f"Minecraft version "
                f"для '{version_id}'."
            )

        loader_detected = _detect_loader(
            version_id
        )

        log_func(
            f"[Mace Launcher] "
            f"Профіль: {username} | "
            f"RAM: {ram_gb}GB"
        )

        log_func(
            f"[Mace] Лоадер: "
            f"{loader_detected.upper()} | "
            f"Minecraft: {mc_version}"
        )

        # JAVA
        java_info = get_java_info(
            mc_version
        )

        java_exe = java_info["path"]
        required_java = java_info["required"]
        actual_java = java_info["actual"]

        log_func(
            f"[Mace] Потрібна Java: "
            f"{required_java}"
        )

        log_func(
            f"[Mace] Java: "
            f"{java_exe}"
        )

        if actual_java is not None:
            log_func(
                f"[Mace] Виявлена Java: "
                f"{actual_java}"
            )

            if actual_java < required_java:
                raise RuntimeError(
                    f"Для Minecraft "
                    f"{mc_version} потрібна "
                    f"Java {required_java}, "
                    f"але знайдена Java "
                    f"{actual_java}."
                )

        else:
            raise RuntimeError(
                f"Не вдалося перевірити "
                f"Java для Minecraft "
                f"{mc_version}."
            )

        player_uuid = str(
            uuid.uuid3(
                uuid.NAMESPACE_DNS,
                username
            )
        )

        launcher_version = get_launcher_version()

        jvm_args = [
            f"-Xmx{ram_gb}G",
            f"-Xms{max(1, ram_gb // 2)}G"
        ]

        options = {
            "username": username,
            "uuid": player_uuid,
            "token": "0",
            "executablePath": java_exe,
            "gameDirectory": version_folder,
            "jvmArguments": jvm_args,
            "launcherName": "Mace Launcher",
            "launcherVersion": launcher_version
        }

        log_func(
            f"[Mace] Версія лаунчера: "
            f"{launcher_version}"
        )

        log_func(
            "[Mace] Генерация "
            "команды запуска..."
        )

        cmd_args = (
            minecraft_launcher_lib.command
            .get_minecraft_command(
                version_id,
                MINECRAFT_DIR,
                options
            )
        )

        if not cmd_args:
            raise RuntimeError(
                "minecraft-launcher-lib "
                "не повернув команду запуску."
            )

        log_func(
            f"[Mace] Команда сформована. "
            f"Аргументів у команді: "
            f"{len(cmd_args)}"
        )

        log_func(
            "[Mace] Старт Java процесу..."
        )

        game_process = subprocess.Popen(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            cwd=version_folder
        )

        thread = threading.Thread(
            target=read_process_output,
            args=(
                game_process.stdout,
                log_func
            ),
            daemon=True
        )

        thread.start()

        monitor_thread = threading.Thread(
            target=_monitor_minecraft_process,
            args=(game_process, version_folder, log_func),
            daemon=True
        )
        monitor_thread.start()

        log_func(
            "[Mace SUCCESS] "
            "Java процес запущено."
        )

    except Exception as e:
        log_func(
            f"[ERROR] "
            f"Помилка запуску гри: {e}"
        )

        log_func(
            traceback.format_exc()
        )


def _open_mace_doctor(instance_dir, log_func=print):
    launcher_dir = os.path.dirname(os.path.abspath(__file__))
    doctor_exe = os.path.join(launcher_dir, "MaceDoctor.exe")
    doctor_py = os.path.join(launcher_dir, "MaceDoctor.py")

    if os.path.isfile(doctor_exe):
        command = [doctor_exe, instance_dir]
    elif os.path.isfile(doctor_py):
        command = [sys.executable, doctor_py, instance_dir]
    else:
        log_func("[Mace Doctor] MaceDoctor.exe/MaceDoctor.py не найден.")
        return False

    try:
        kwargs = {"cwd": launcher_dir}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.Popen(command, **kwargs)
        log_func("[Mace Doctor] Minecraft завершился с ошибкой.")
        log_func("[Mace Doctor] Открываю Mace Doctor...")
        return True
    except Exception as e:
        log_func(f"[Mace Doctor] Не удалось открыть Mace Doctor: {e}")
        return False


def _monitor_minecraft_process(process, instance_dir, log_func=print):
    global game_process

    try:
        exit_code = process.wait()
        if game_process_user_stopped:
            log_func("[Mace] Minecraft был остановлен пользователем.")
            return

        if exit_code != 0:
            _open_mace_doctor(instance_dir, log_func)
        else:
            log_func("[Mace] Minecraft завершился нормально.")
    except Exception as e:
        log_func(f"[Mace] Ошибка мониторинга Minecraft: {e}")
    finally:
        if game_process is process:
            game_process = None


# ============================================================
# JSON NORMALIZATION
# ============================================================

def _normalize_launcher_json_arguments(
    version_data
):
    if not isinstance(
        version_data,
        dict
    ):
        return version_data

    arguments = version_data.get(
        "arguments"
    )

    if not isinstance(
        arguments,
        dict
    ):
        return version_data

    for section in (
        "jvm",
        "game"
    ):
        items = arguments.get(
            section
        )

        if not isinstance(
            items,
            list
        ):
            continue

        fixed_items = []

        for item in items:
            if isinstance(
                item,
                str
            ):
                fixed_items.append(item)
                continue

            if not isinstance(
                item,
                dict
            ):
                continue

            fixed = dict(item)

            if (
                "value" not in fixed
                and "values" in fixed
            ):
                values = fixed.get(
                    "values"
                )

                if isinstance(
                    values,
                    (list, tuple)
                ):
                    fixed["value"] = (
                        values[0]
                        if len(values) == 1
                        else list(values)
                    )

                elif isinstance(
                    values,
                    str
                ):
                    fixed["value"] = values

                fixed.pop(
                    "values",
                    None
                )

            if (
                "value" in fixed
                or "rules" in fixed
                or "compatibilityRules" in fixed
            ):
                fixed_items.append(fixed)

        arguments[section] = fixed_items

    return version_data


# ============================================================
# GAME STATUS
# ============================================================

def is_game_running():
    global game_process

    if game_process is not None:
        if game_process.poll() is None:
            return True

        game_process = None

    return False


def stop_minecraft(
    log_func=print
):
    global game_process, game_process_user_stopped

    if is_game_running():
        try:
            game_process_user_stopped = True
            game_process.terminate()

            log_func(
                "[Mace] "
                "Процес гри зупинено."
            )

        except Exception as e:
            log_func(
                f"[Mace ERROR] "
                f"Помилка: {e}"
            )

        game_process = None