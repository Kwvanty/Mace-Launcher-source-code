import os
import re
import json
import shutil
import ssl
import subprocess
import urllib.request


def _urlopen_with_ssl_bypass(url, timeout=20):
    ctx = ssl._create_unverified_context()
    request = urllib.request.Request(url, headers={"User-Agent": "MaceLauncher/1.0"})
    return urllib.request.urlopen(request, context=ctx, timeout=timeout)


def _normalize_neoforge_version(mc_version):
    version = str(mc_version).strip()
    if version.startswith("1."):
        version = version[2:]
    return version


def _get_neoforge_versions():
    url = "https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/neoforge"
    try:
        with _urlopen_with_ssl_bypass(url, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data.get("versions", [])
    except Exception:
        return []


def _find_neoforge_version(mc_version):
    versions = _get_neoforge_versions()
    if not versions:
        return None
    normalized = _normalize_neoforge_version(mc_version)
    target_parts = tuple(int(part) for part in normalized.split(".") if part.isdigit())
    matches = []

    for v in versions:
        v_str = str(v)
        v_parts = tuple(int(part) for part in re.split(r"[-.]", v_str) if part.isdigit())
        if not v_parts:
            continue
        if len(v_parts) >= len(target_parts) and v_parts[:len(target_parts)] == target_parts:
            matches.append((v_parts, v_str))

    if not matches:
        return None

    best_tuple, best_version = max(matches, key=lambda item: item[0])
    return best_version


def install(version_name:str,mc_version:str,minecraft_dir:str)->tuple:
    try:
        version_folder=os.path.join(minecraft_dir,"versions",version_name)
        os.makedirs(version_folder,exist_ok=True)
        if not str(mc_version).startswith("1.21"):
            return False,f"NeoForge поддерживается этим загрузчиком только для Minecraft 1.21.x."
        neoforge_version=_find_neoforge_version(mc_version)
        if not neoforge_version:
            return False,f"Не удалось найти NeoForge для Minecraft {mc_version}."
        installer_url=f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{neoforge_version}/neoforge-{neoforge_version}-installer.jar"
        installer_path=os.path.join(minecraft_dir,"neoforge-installer.jar")
        with _urlopen_with_ssl_bypass(installer_url, timeout=30) as response:
            with open(installer_path, "wb") as f:
                shutil.copyfileobj(response, f)
        subprocess.run([
            "java","-jar",installer_path,
            "--installClient",
            minecraft_dir
        ],check=True)
        os.remove(installer_path)
        installed_json=None
        versions_dir=os.path.join(minecraft_dir,"versions")
        for folder in os.listdir(versions_dir):
            folder_path=os.path.join(versions_dir,folder)
            json_path=os.path.join(folder_path,f"{folder}.json")
            if not os.path.isfile(json_path):
                continue
            try:
                with open(json_path,"r",encoding="utf-8") as f:
                    data=json.load(f)
                text=json.dumps(data).lower()
                if "neoforge" in text and mc_version in text:
                    installed_json=json_path
                    break
            except Exception:
                continue
        if not installed_json:
            return False,"NeoForge установщик завершился, но профиль NeoForge не найден."
        with open(installed_json,"r",encoding="utf-8") as f:
            data=json.load(f)
        data["id"]=version_name
        if not data.get("inheritsFrom"):
            data["inheritsFrom"] = mc_version
        if not data.get("jar"):
            data["jar"] = mc_version
        target_json=os.path.join(version_folder,f"{version_name}.json")
        with open(target_json,"w",encoding="utf-8") as f:
            json.dump(data,f,indent=4)
        source_folder=os.path.dirname(installed_json)
        for name in os.listdir(source_folder):
            if name.endswith(".jar"):
                source=os.path.join(source_folder,name)
                target=os.path.join(version_folder,name)
                if not os.path.exists(target):
                    shutil.copy2(source,target)
        return True,f"NeoForge {neoforge_version} для Minecraft {mc_version} установлен."
    except subprocess.CalledProcessError as e:
        return False,f"NeoForge installer завершился с ошибкой: {e}"
    except Exception as e:
        return False,f"Ошибка установки NeoForge: {e}"