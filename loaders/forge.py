import os
import re
import json
import shutil
import subprocess
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET


# ============================================================
# HELPERS
# ============================================================

USER_AGENT = "MaceLauncher/1.0"


def _download(url, destination):
    """
    Скачивает файл с Forge Maven.
    """
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=60
    ) as response:

        with open(
            destination,
            "wb"
        ) as output:

            shutil.copyfileobj(
                response,
                output
            )


def _version_key(version):
    """
    Сортировка Forge-версий.

    Например:
        47.3.0
        47.3.1
        47.4.0
    """

    parts = []

    for part in re.findall(
        r"\d+",
        version or ""
    ):
        try:
            parts.append(
                int(part)
            )
        except Exception:
            parts.append(0)

    return tuple(parts)


def _get_forge_versions(mc_version):
    """
    Получает все Forge версии,
    совместимые с конкретным Minecraft.
    """

    metadata_url = (
        "https://maven.minecraftforge.net/"
        "net/minecraftforge/forge/"
        "maven-metadata.xml"
    )

    request = urllib.request.Request(
        metadata_url,
        headers={
            "User-Agent": USER_AGENT
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=20
    ) as response:

        xml_data = response.read().decode(
            "utf-8"
        )

    root = ET.fromstring(
        xml_data
    )

    result = []

    prefix = mc_version + "-"

    for element in root.iter("version"):

        value = element.text

        if not value:
            continue

        value = value.strip()

        if value.startswith(prefix):
            result.append(value)

    result = sorted(
        set(result),
        key=_version_key
    )

    return result


def _get_preferred_forge_version(mc_version):
    """
    Выбирает последнюю доступную Forge
    для Minecraft.
    """

    versions = _get_forge_versions(
        mc_version
    )

    if not versions:
        return None

    return versions[-1]


def _find_installed_forge_folder(
    minecraft_dir,
    mc_version,
    forge_version
):
    """
    После работы Installer ищет созданную
    Forge-папку.
    """

    versions_dir = os.path.join(
        minecraft_dir,
        "versions"
    )

    if not os.path.isdir(
        versions_dir
    ):
        return None

    expected_names = [
        f"forge-{mc_version}-{forge_version}",
        f"{mc_version}-forge-{forge_version}",
    ]

    # --------------------------------------------------------
    # Сначала ищем точное имя
    # --------------------------------------------------------

    for name in expected_names:

        path = os.path.join(
            versions_dir,
            name
        )

        if not os.path.isdir(path):
            continue

        json_path = os.path.join(
            path,
            f"{name}.json"
        )

        if os.path.exists(
            json_path
        ):
            return name

    # --------------------------------------------------------
    # Более универсальный поиск
    # --------------------------------------------------------

    possible = []

    for name in os.listdir(
        versions_dir
    ):

        lower = name.lower()

        if (
            "forge" not in lower
            or mc_version.lower() not in lower
        ):
            continue

        path = os.path.join(
            versions_dir,
            name
        )

        if not os.path.isdir(path):
            continue

        json_path = os.path.join(
            path,
            f"{name}.json"
        )

        if os.path.exists(
            json_path
        ):
            possible.append(name)

    if not possible:
        return None

    possible.sort(
        key=_version_key
    )

    return possible[-1]


def _copy_installed_forge_profile(
    minecraft_dir,
    installed_name,
    target_name
):
    """
    Создаёт Mace-профиль на основе настоящего
    Forge-профиля, созданного Forge Installer.

    Важно:

    Мы НЕ создаём упрощённый Forge JSON.

    Сохраняем аргументы, libraries, mainClass,
    inheritsFrom и остальные данные Forge.
    """

    versions_dir = os.path.join(
        minecraft_dir,
        "versions"
    )

    source_dir = os.path.join(
        versions_dir,
        installed_name
    )

    target_dir = os.path.join(
        versions_dir,
        target_name
    )

    source_json = os.path.join(
        source_dir,
        f"{installed_name}.json"
    )

    target_json = os.path.join(
        target_dir,
        f"{target_name}.json"
    )

    if not os.path.isdir(
        source_dir
    ):
        return False, (
            "Forge Installer не створив "
            "папку профілю."
        )

    if not os.path.exists(
        source_json
    ):
        return False, (
            "Forge JSON після встановлення "
            "не знайдено."
        )

    os.makedirs(
        target_dir,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Копируем JAR и остальные файлы
    # --------------------------------------------------------

    for item in os.listdir(
        source_dir
    ):

        source_path = os.path.join(
            source_dir,
            item
        )

        target_path = os.path.join(
            target_dir,
            item
        )

        if item == f"{installed_name}.json":
            continue

        if item == f"{installed_name}.jar":

            if os.path.exists(
                target_path
            ):
                os.remove(
                    target_path
                )

            shutil.copy2(
                source_path,
                os.path.join(
                    target_dir,
                    f"{target_name}.jar"
                )
            )

            continue

        if os.path.isdir(
            source_path
        ):

            if os.path.exists(
                target_path
            ):
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

    # --------------------------------------------------------
    # Настоящий Forge JSON
    # --------------------------------------------------------

    with open(
        source_json,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    data["id"] = target_name

    # Некоторые Forge-профили могут ссылаться
    # на собственный старый ID через jar.

    if data.get("jar") == installed_name:
        data["jar"] = target_name

    # --------------------------------------------------------
    # Безопасно заменяем только точные ссылки
    # на старый профиль.
    # --------------------------------------------------------

    def replace_exact(value):

        if isinstance(value, str):

            if value == installed_name:
                return target_name

            return value

        if isinstance(value, list):

            return [
                replace_exact(item)
                for item in value
            ]

        if isinstance(value, dict):

            return {
                key: replace_exact(item)
                for key, item in value.items()
            }

        return value

    data = replace_exact(data)

    data["id"] = target_name

    with open(
        target_json,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False
        )

    return True, target_dir


# ============================================================
# MAIN INSTALL
# ============================================================

def install(
    version_name: str,
    mc_version: str,
    minecraft_dir: str
) -> tuple:
    """
    Устанавливает Forge для выбранной версии Minecraft.

    Сохраняет старую механику Mace Launcher:

      - version_name остаётся именем сборки;
      - сборка создаётся в versions/version_name;
      - mods/config/resourcepacks/shaderpacks создаются;
      - Forge устанавливается официальным Installer;
      - используется подходящая Java;
      - настоящий Forge JSON сохраняется.

    Forge Installer временно хранится в:

        Mace Launcher/Forge/

    После установки Installer автоматически удаляется.
    """

    installer_path = None
    installed_forge_name = None

    try:

        # ----------------------------------------------------
        # Проверки
        # ----------------------------------------------------

        if not version_name:
            return False, (
                "Ім'я Forge-версії не задано."
            )

        if not mc_version:
            return False, (
                "Версія Minecraft не задана."
            )

        versions_dir = os.path.join(
            minecraft_dir,
            "versions"
        )

        version_folder = os.path.join(
            versions_dir,
            version_name
        )

        if os.path.exists(
            version_folder
        ):
            return False, (
                f"Версія '{version_name}' "
                f"вже існує!"
            )

        os.makedirs(
            versions_dir,
            exist_ok=True
        )

        # ----------------------------------------------------
        # Java
        # ----------------------------------------------------

        from launcher_core import (
            find_suitable_java,
            get_required_java_version
        )

        required_java = get_required_java_version(
            mc_version
        )

        java_bin = find_suitable_java(
            mc_version
        )

        java_check = subprocess.run(
            [
                java_bin,
                "-version"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
            check=False
        )

        java_output = (
            java_check.stdout
            or ""
        )

        if not java_output:

            return False, (
                f"Не вдалося перевірити "
                f"Java для Minecraft "
                f"{mc_version}."
            )

        # ----------------------------------------------------
        # Forge version
        # ----------------------------------------------------

        forge_version = (
            _get_preferred_forge_version(
                mc_version
            )
        )

        if not forge_version:

            return False, (
                f"Не вдалося знайти "
                f"сумісний Forge для "
                f"Minecraft {mc_version}."
            )

        # ----------------------------------------------------
        # Installer URL
        # ----------------------------------------------------

        installer_url = (
            "https://maven.minecraftforge.net/"
            "net/minecraftforge/forge/"
            f"{forge_version}/"
            f"forge-{forge_version}-installer.jar"
        )

        # ----------------------------------------------------
        # Forge folder
        # ----------------------------------------------------

        launcher_dir = os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )

        forge_dir = os.path.join(
            launcher_dir,
            "Forge"
        )

        os.makedirs(
            forge_dir,
            exist_ok=True
        )

        # ----------------------------------------------------
        # Installer path
        # ----------------------------------------------------

        installer_path = os.path.join(
            forge_dir,
            f"forge_installer_"
            f"{version_name}.jar"
        )

        # ----------------------------------------------------
        # Download
        # ----------------------------------------------------

        try:

            _download(
                installer_url,
                installer_path
            )

        except urllib.error.HTTPError as e:

            return False, (
                f"Forge Installer "
                f"недоступний "
                f"(HTTP {e.code}). "
                f"Версія Forge: "
                f"{forge_version}"
            )

        except Exception as e:

            return False, (
                f"Не вдалося завантажити "
                f"Forge Installer: {e}"
            )

        if not os.path.exists(
            installer_path
        ):

            return False, (
                "Forge Installer "
                "не був завантажений."
            )

        # ----------------------------------------------------
        # Installer
        # ----------------------------------------------------

        installer_result = subprocess.run(
            [
                java_bin,
                "-jar",
                installer_path,
                "--installClient",
                minecraft_dir
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False
        )

        installer_output = (
            installer_result.stdout
            or ""
        )

        if installer_result.returncode != 0:

            return False, (
                "Forge Installer завершився "
                f"з кодом "
                f"{installer_result.returncode}.\n"
                f"{installer_output[-3000:]}"
            )

        # ----------------------------------------------------
        # Find installed Forge
        # ----------------------------------------------------

        installed_forge_name = (
            _find_installed_forge_folder(
                minecraft_dir,
                mc_version,
                forge_version
            )
        )

        if not installed_forge_name:

            return False, (
                "Forge Installer завершився, "
                "але Mace не знайшов "
                "створений Forge-профіль."
            )

        # ----------------------------------------------------
        # Copy REAL Forge profile
        # ----------------------------------------------------

        success, result = (
            _copy_installed_forge_profile(
                minecraft_dir,
                installed_forge_name,
                version_name
            )
        )

        if not success:
            return False, result

        # ----------------------------------------------------
        # Mace directories
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Verify JSON
        # ----------------------------------------------------

        final_json = os.path.join(
            version_folder,
            f"{version_name}.json"
        )

        if not os.path.exists(
            final_json
        ):

            return False, (
                "Forge встановився, але "
                "Mace JSON не створився."
            )

        # ----------------------------------------------------
        # Cleanup installer
        # ----------------------------------------------------

        if os.path.exists(
            installer_path
        ):

            try:

                os.remove(
                    installer_path
                )

            except Exception:
                pass

        installer_path = None

        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        return True, (
            f"Forge для Minecraft "
            f"{mc_version} успішно встановлено!\n"
            f"Forge: {forge_version}\n"
            f"Java: {required_java}\n"
            f"Профіль: {version_name}"
        )

    except Exception as e:

        return False, (
            f"Помилка встановлення Forge: "
            f"{str(e)}"
        )

    finally:

        # ----------------------------------------------------
        # Удаляем Installer даже при ошибке
        # ----------------------------------------------------

        if (
            installer_path
            and os.path.exists(
                installer_path
            )
        ):

            try:

                os.remove(
                    installer_path
                )

            except Exception:
                pass