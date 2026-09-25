import json
import os
import threading
import urllib.parse
import urllib.request

MODRINTH_API_URL = "https://api.modrinth.com/v2"
USER_AGENT = "Kuvanty/MaceLauncher/1.0 (Contact: kuvanty.dev@gmail.com; https://github.com/Kuvanty/MaceLauncher)"


def _normalize_loader_name(loader):
    value = (loader or "").strip().lower()
    if not value or value in ["all", "any"]:
        return ""
    aliases = {
        "forge": "forge",
        "neoforge": "neoforge",
        "fabric": "fabric",
        "quilt": "quilt",
        "curseforge": "forge",
    }
    return aliases.get(value, value)


def _build_search_facets(loader="", version="", category=""):
    facets = []
    norm_loader = _normalize_loader_name(loader)
    if norm_loader:
        facets.append([f"categories:{norm_loader}"])
    if version and str(version).lower() not in ["all", ""]:
        facets.append([f"versions:{version}"])
    if category and str(category).lower() not in ["all", ""]:
        facets.append([f"categories:{str(category).lower()}"])
    return facets


def search_mods_api(query="", loader="", version="", category="", limit=12, offset=0):
    """Живий пошук модів через Modrinth API з коректними facet-фільтрами."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    try:
        clean_query = (query or "").strip() or "minecraft"
        params = {"query": clean_query, "limit": max(1, int(limit)), "offset": max(0, int(offset))}

        facets = _build_search_facets(loader, version, category)
        if facets:
            params["facets"] = json.dumps(facets)

        url = f"{MODRINTH_API_URL}/search?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                hits = data.get("hits", [])
                results = []
                for item in hits:
                    results.append({
                        "id": item.get("project_id", ""),
                        "slug": item.get("slug", ""),
                        "title": item.get("title", "Без назви"),
                        "description": item.get("description", "Опис відсутній."),
                        "icon_url": item.get("icon_url", ""),
                        "downloads": item.get("downloads", 0),
                        "author": item.get("author", "Невідомо"),
                        "versions": item.get("versions", []),
                        "categories": item.get("categories", []),
                    })
                return True, results
    except urllib.error.HTTPError as e:
        print(f"Modrinth API HTTP Error {e.code}: {e.reason}")
    except Exception as e:
        print(f"Modrinth API Search Error: {e}")

    return False, []


def download_mod_file_async(
    project_id_or_slug,
    target_dir,
    callback=None,
    loader="fabric",
    minecraft_version=""
):
    """Скачивает строго совместимый с loader + Minecraft мод."""

    def worker():
        os.makedirs(target_dir, exist_ok=True)

        try:
            params = {}

            # Modrinth принимает JSON-массивы для этих параметров.
            if loader:
                params["loaders"] = json.dumps([loader])

            if minecraft_version:
                params["game_versions"] = json.dumps([minecraft_version])

            query = urllib.parse.urlencode(params)

            url = (
                f"{MODRINTH_API_URL}/project/"
                f"{urllib.parse.quote(str(project_id_or_slug), safe='')}/version"
            )

            if query:
                url += "?" + query

            print(
                f"[ModBrowser] Download versions: "
                f"loader={loader}, "
                f"minecraft={minecraft_version}"
            )

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                }
            )

            with urllib.request.urlopen(req, timeout=12) as response:
                if response.status != 200:
                    raise RuntimeError(
                        f"Modrinth HTTP {response.status}"
                    )

                versions_data = json.loads(
                    response.read().decode("utf-8")
                )

            if not versions_data:
                raise RuntimeError(
                    f"Для мода нет версии "
                    f"под {loader} + Minecraft {minecraft_version}"
                )

            # Дополнительная проверка.
            # Даже если API что-то вернуло, убеждаемся,
            # что версия действительно подходит.
            compatible_versions = []

            for version in versions_data:

                version_loaders = [
                    str(x).lower()
                    for x in version.get("loaders", [])
                ]

                game_versions = [
                    str(x)
                    for x in version.get("game_versions", [])
                ]

                if loader:
                    if loader.lower() not in version_loaders:
                        continue

                if minecraft_version:
                    if minecraft_version not in game_versions:
                        continue

                compatible_versions.append(version)

            if not compatible_versions:
                raise RuntimeError(
                    f"Не найден файл под "
                    f"{loader} / {minecraft_version}"
                )

            # Самая свежая подходящая версия обычно идёт первой.
            selected_version = compatible_versions[0]

            files = selected_version.get("files", []) or []

            if not files:
                raise RuntimeError(
                    "У найденной версии нет файлов."
                )

            # Берём primary-файл.
            file_info = next(
                (
                    f for f in files
                    if f.get("primary") is True
                ),
                files[0]
            )

            file_url = file_info.get("url")
            filename = file_info.get("filename")

            if not file_url:
                raise RuntimeError(
                    "Modrinth не вернул URL файла."
                )

            if not filename:
                filename = (
                    f"{project_id_or_slug}.jar"
                )

            # Последняя страховка:
            # скачиваем только JAR.
            if not filename.lower().endswith(".jar"):
                raise RuntimeError(
                    f"Найденный файл не является JAR: {filename}"
                )

            dest_path = os.path.join(
                target_dir,
                filename
            )

            print(
                f"[ModBrowser] Installing: {filename}"
            )

            file_req = urllib.request.Request(
                file_url,
                headers={
                    "User-Agent": USER_AGENT
                }
            )

            with (
                urllib.request.urlopen(
                    file_req,
                    timeout=30
                ) as f_resp,
                open(dest_path, "wb") as out_file
            ):
                while True:
                    chunk = f_resp.read(1024 * 1024)

                    if not chunk:
                        break

                    out_file.write(chunk)

            if callback:
                callback(
                    True,
                    f"Мод '{filename}' успешно установлен!"
                )

        except Exception as e:

            print(
                f"[ModBrowser] Download error: {e}"
            )

            if callback:
                callback(
                    False,
                    f"Ошибка загрузки: {e}"
                )

    threading.Thread(
        target=worker,
        daemon=True,
        name="ModrinthModDownload"
    ).start()

    def worker():
        os.makedirs(target_dir, exist_ok=True)
        try:
            url = f"{MODRINTH_API_URL}/project/{project_id_or_slug}/version"
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    versions_data = json.loads(response.read().decode("utf-8"))
                    if versions_data:
                        file_info = None
                        for version in versions_data:
                            files = version.get("files", []) or []
                            for candidate in files:
                                if candidate.get("primary") is True:
                                    file_info = candidate
                                    break
                            if file_info is not None:
                                break
                        if file_info is None and versions_data:
                            files = versions_data[0].get("files", []) or []
                            if files:
                                file_info = files[0]

                        if file_info is not None:
                            file_url = file_info.get("url")
                            filename = file_info.get("filename") or f"{project_id_or_slug}.jar"

                            dest_path = os.path.join(target_dir, filename)
                            file_req = urllib.request.Request(
                                file_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
                            )
                            with (
                                urllib.request.urlopen(file_req, timeout=25) as f_resp,
                                open(dest_path, "wb") as out_file,
                            ):
                                out_file.write(f_resp.read())

                            if callback:
                                callback(True, f"Мод '{filename}' успішно встановлено!")
                            return
            if callback:
                callback(False, "Не вдалося знайти файл мода.")
        except Exception:
            if callback:
                callback(False, "Помилка завантаження файлу мода.")

    threading.Thread(target=worker, daemon=True).start()


def is_mod_installed(mod_title_or_slug, target_dir):
    """Перевіряє, чи встановлено мод у папці призначення."""
    if not os.path.exists(target_dir):
        return False
    slug_clean = (mod_title_or_slug or "").lower().replace(" ", "")
    for f in os.listdir(target_dir):
        if f.endswith(".jar") or f.endswith(".jar.disabled"):
            f_clean = f.lower().replace(" ", "")
            if slug_clean and slug_clean in f_clean:
                return True
    return False
