import os
import shutil
import json
import minecraft_launcher_lib

def install(version_name: str, mc_version: str, minecraft_dir: str) -> tuple:
    """
    Встановлює Forge для вказаної версії Minecraft та створює ізольовану структуру файлів.
    """
    try:
        version_folder = os.path.join(minecraft_dir, "versions", version_name)
        os.makedirs(version_folder, exist_ok=True)
        
        # Встановлюємо базову ванільну версію для Forge
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
                
        # Копіюємо jar-файл базової версії, якщо він є
        base_jar = os.path.join(minecraft_dir, "versions", mc_version, f"{mc_version}.jar")
        target_jar = os.path.join(version_folder, f"{version_name}.jar")
        if os.path.exists(base_jar) and not os.path.exists(target_jar):
            shutil.copy2(base_jar, target_jar)
            
        return True, "Успіх"
        
    except Exception as e:
        return False, str(e)