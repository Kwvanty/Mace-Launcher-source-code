import os
import shutil
import json
import minecraft_launcher_lib

def install(version_name: str, mc_version: str, minecraft_dir: str) -> tuple:
    """
    Автоматично завантажує та встановлює Fabric Loader для будь-якої версії Minecraft,
    після чого розгортає його в ізольовану папку збірки.
    """
    try:
        versions_dir = os.path.join(minecraft_dir, "versions")
        version_folder = os.path.join(versions_dir, version_name)
        os.makedirs(version_folder, exist_ok=True)

        # Фіксуємо список папок до завантаження
        before_folders = set(os.listdir(versions_dir)) if os.path.exists(versions_dir) else set()

        # 1. Завантажуємо та встановлюємо Fabric через бібліотеку
        try:
            minecraft_launcher_lib.fabric.install_fabric(
                minecraft_version=mc_version,
                minecraft_directory=minecraft_dir
            )
        except Exception as e:
            return False, f"Помилка завантаження Fabric з сервера для версії {mc_version}: {str(e)}"

        # 2. Виявляємо нову згенеровану папку Fabric
        after_folders = set(os.listdir(versions_dir))
        new_folders = list(after_folders - before_folders)

        base_fabric_version = None
        if new_folders:
            for folder in new_folders:
                if "fabric-loader" in folder.lower():
                    base_fabric_version = folder
                    break

        # Резервний пошук папки Fabric
        if not base_fabric_version:
            for v in os.listdir(versions_dir):
                if "fabric-loader" in v.lower() and mc_version in v and v != version_name:
                    base_fabric_version = v
                    break

        if not base_fabric_version:
            return False, f"Не вдалося знайти згенеровану папку Fabric для версії {mc_version}!"

        # 3. Скопіювати вміст Fabric у нашу ізольовану папку збірки
        src_dir = os.path.join(versions_dir, base_fabric_version)
        for item in os.listdir(src_dir):
            s_item = os.path.join(src_dir, item)
            d_item = os.path.join(version_folder, item)
            if os.path.isdir(s_item):
                shutil.copytree(s_item, d_item, dirs_exist_ok=True)
            else:
                shutil.copy2(s_item, d_item)

        # 4. Перейменувати JSON та JAR під назву збірки
        old_json = os.path.join(version_folder, f"{base_fabric_version}.json")
        new_json = os.path.join(version_folder, f"{version_name}.json")
        if os.path.exists(old_json):
            os.rename(old_json, new_json)
            with open(new_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data["id"] = version_name
            with open(new_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)

        old_jar = os.path.join(version_folder, f"{base_fabric_version}.jar")
        new_jar = os.path.join(version_folder, f"{version_name}.jar")
        if os.path.exists(old_jar):
            os.rename(old_jar, new_jar)

        # 5. Створити стандартні ізольовані підпапки
        os.makedirs(os.path.join(version_folder, "mods"), exist_ok=True)
        os.makedirs(os.path.join(version_folder, "resourcepacks"), exist_ok=True)
        os.makedirs(os.path.join(version_folder, "shaderpacks"), exist_ok=True)
        os.makedirs(os.path.join(version_folder, "config"), exist_ok=True)

        return True, f"Fabric ({mc_version}) успішно налаштовано для збірки '{version_name}'!"

    except Exception as e:
        return False, f"Помилка створення Fabric: {str(e)}"