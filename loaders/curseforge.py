import os
import shutil
import json
import zipfile
import minecraft_launcher_lib

def install(version_name: str, modpack_zip_path: str, minecraft_dir: str) -> tuple:
    """
    Встановлює CurseForge модпак із ZIP-архіву, розпаковує overrides в ізольовану папку
    та налаштовує відповідний завантажувач (Forge, NeoForge або Fabric).
    """
    temp_extract_dir = None
    try:
        if not os.path.exists(modpack_zip_path):
            return False, f"Архів модпаку не знайдено: {modpack_zip_path}"

        version_folder = os.path.join(minecraft_dir, "versions", version_name)
        os.makedirs(version_folder, exist_ok=True)

        # Тимчасова папка для розпакування архіву модпаку
        temp_extract_dir = os.path.join(minecraft_dir, "versions", f"temp_{version_name}")
        os.makedirs(temp_extract_dir, exist_ok=True)

        with zipfile.ZipFile(modpack_zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_dir)

        manifest_path = os.path.join(temp_extract_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            return False, "У архіві відсутній файл manifest.json (це не валідний CurseForge модпак)."

        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        mc_version = manifest.get("minecraft", {}).get("version")
        modloaders = manifest.get("minecraft", {}).get("modloaders", [])
        
        loader_type = "vanilla"
        if modloaders:
            primary_loader = modloaders[0].get("id", "").lower()
            if "forge" in primary_loader:
                loader_type = "forge"
            elif "neoforge" in primary_loader:
                loader_type = "neoforge"
            elif "fabric" in primary_loader:
                loader_type = "fabric"

        # Встановлюємо базу залежно від типу завантажувача у маніфесті
        if loader_type in ["forge", "neoforge"]:
            minecraft_launcher_lib.install.install_minecraft_version(mc_version, minecraft_dir)
            base_json_path = os.path.join(minecraft_dir, "versions", mc_version, f"{mc_version}.json")
            target_json_path = os.path.join(version_folder, f"{version_name}.json")
            
            if os.path.exists(base_json_path):
                with open(base_json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                data["id"] = version_name
                data["mainClass"] = "cpw.mods.modlauncher.Launcher"
                with open(target_json_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
            else:
                data = {
                    "id": version_name,
                    "inheritsFrom": mc_version,
                    "mainClass": "cpw.mods.modlauncher.Launcher",
                    "type": "release",
                    "assets": mc_version,
                    "libraries": []
                }
                with open(target_json_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
                    
            base_jar = os.path.join(minecraft_dir, "versions", mc_version, f"{mc_version}.jar")
            target_jar = os.path.join(version_folder, f"{version_name}.jar")
            if os.path.exists(base_jar) and not os.path.exists(target_jar):
                shutil.copy2(base_jar, target_jar)

        elif loader_type == "fabric":
            minecraft_launcher_lib.fabric.install_fabric(
                minecraft_version=mc_version,
                minecraft_directory=minecraft_dir
            )
            versions_dir = os.path.join(minecraft_dir, "versions")
            base_fabric_version = None
            if os.path.exists(versions_dir):
                for v in os.listdir(versions_dir):
                    if "fabric-loader" in v.lower() and mc_version in v:
                        base_fabric_version = v
                        break
            if base_fabric_version:
                src_dir = os.path.join(versions_dir, base_fabric_version)
                if os.path.exists(version_folder):
                    shutil.rmtree(version_folder)
                    os.makedirs(version_folder, exist_ok=True)
                
                for item in os.listdir(src_dir):
                    s_item = os.path.join(src_dir, item)
                    d_item = os.path.join(version_folder, item)
                    if os.path.isdir(s_item):
                        shutil.copytree(s_item, d_item, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s_item, d_item)
                        
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
        else:
            minecraft_launcher_lib.install.install_minecraft_version(mc_version, minecraft_dir)

        # Копіюємо папки overrides (моди, конфи, шейдери) безпосередньо у папку збірки
        overrides_folder_name = manifest.get("overrides", "overrides")
        overrides_src = os.path.join(temp_extract_dir, overrides_folder_name)
        if os.path.exists(overrides_src):
            for item in os.listdir(overrides_src):
                s_path = os.path.join(overrides_src, item)
                d_path = os.path.join(version_folder, item)
                if os.path.isdir(s_path):
                    shutil.copytree(s_path, d_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(s_path, d_path)

        # Прибираємо тимчасові файли
        if temp_extract_dir and os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir, ignore_errors=True)

        # Гарантуємо наявність усіх стандартних підпапок
        os.makedirs(os.path.join(version_folder, "mods"), exist_ok=True)
        os.makedirs(os.path.join(version_folder, "resourcepacks"), exist_ok=True)
        os.makedirs(os.path.join(version_folder, "shaderpacks"), exist_ok=True)
        os.makedirs(os.path.join(version_folder, "config"), exist_ok=True)

        return True, f"Модпак CurseForge успішно розгорнуто для Minecraft {mc_version}!"

    except Exception as e:
        if temp_extract_dir and os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
        return False, str(e)