# RPloader.py
# Mace Launcher — Resource Pack Loader
# Работа с ресурс-паками через Modrinth API

import json
import os
import urllib.parse
import urllib.request
import urllib.error


MODRINTH_API = "https://api.modrinth.com/v2"


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def _request(url):
    """Выполняет GET-запрос к Modrinth API и возвращает JSON."""

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MaceLauncher/1.0",
            "Accept": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)

    except urllib.error.HTTPError as e:
        print(f"[RPloader] HTTP ошибка: {e.code}")
        return None

    except urllib.error.URLError as e:
        print(f"[RPloader] Ошибка соединения: {e.reason}")
        return None

    except Exception as e:
        print(f"[RPloader] Ошибка: {e}")
        return None


# ============================================================
# ПОИСК
# ============================================================

def search_resource_packs(
    query="",
    minecraft_version=None,
    limit=20,
    offset=0
):
    """
    Ищет ресурс-паки на Modrinth.

    query:
        Текст поиска. Например: "Faithful"

    minecraft_version:
        Версия Minecraft. Например: "1.21.1"

    limit:
        Максимальное количество результатов.

    Возвращает список словарей.
    """

    params = {
        "query": query,
        "limit": limit,
        "offset": offset,

        # Ищем только resource pack
        "facets": json.dumps([
            ["project_type:resourcepack"]
        ])
    }

    # Если указана версия Minecraft,
    # добавляем её в фильтр.
    if minecraft_version:
        params["facets"] = json.dumps([
            ["project_type:resourcepack"],
            [f"versions:{minecraft_version}"]
        ])

    url = (
        f"{MODRINTH_API}/search?"
        f"{urllib.parse.urlencode(params)}"
    )

    data = _request(url)

    if not data:
        return []

    results = []

    for hit in data.get("hits", []):
        results.append({
            "id": hit.get("project_id"),
            "slug": hit.get("slug"),
            "name": hit.get("title"),
            "description": hit.get("description"),
            "icon_url": hit.get("icon_url"),
            "author": hit.get("author"),
            "downloads": hit.get("downloads", 0),
            "follows": hit.get("follows", 0),
            "date_created": hit.get("date_created"),
            "date_modified": hit.get("date_modified"),
            "project_type": hit.get("project_type"),
            "website": hit.get("website_url")
        })

    return results


# ============================================================
# ИНФОРМАЦИЯ О РЕСУРС-ПАКЕ
# ============================================================

def get_resource_pack(project_id):
    """
    Получает полную информацию о ресурс-паке.

    project_id:
        ID проекта Modrinth.

    Например:
        get_resource_pack("...")
    """

    url = f"{MODRINTH_API}/project/{project_id}"

    data = _request(url)

    if not data:
        return None

    return data


# ============================================================
# ВЕРСИИ РЕСУРС-ПАКА
# ============================================================

def get_resource_pack_versions(
    project_id,
    minecraft_version=None
):
    """
    Получает версии конкретного ресурс-пака.

    Если minecraft_version указана,
    возвращаются только совместимые версии.
    """

    params = {}

    if minecraft_version:
        params["game_versions"] = json.dumps([
            minecraft_version
        ])

    params["loaders"] = json.dumps([
        "minecraft"
    ])

    url = (
        f"{MODRINTH_API}/project/"
        f"{project_id}/version?"
        f"{urllib.parse.urlencode(params)}"
    )

    data = _request(url)

    if not data:
        return []

    return data


# ============================================================
# ПОЛУЧЕНИЕ ФАЙЛА
# ============================================================

def get_download_file(
    project_id,
    minecraft_version=None
):
    """
    Находит подходящий файл ресурс-пака.

    Возвращает:

    {
        "url": "...",
        "filename": "...",
        "size": ...,
        "sha1": "...",
        "version_id": "..."
    }

    или None, если файл не найден.
    """

    versions = get_resource_pack_versions(
        project_id,
        minecraft_version
    )

    if not versions:
        return None

    # Берём первую подходящую версию.
    version = versions[0]

    files = version.get("files", [])

    if not files:
        return None

    # Предпочитаем основной файл.
    primary_file = None

    for file in files:
        if file.get("primary"):
            primary_file = file
            break

    if primary_file is None:
        primary_file = files[0]

    hashes = primary_file.get("hashes", {})

    return {
        "url": primary_file.get("url"),
        "filename": primary_file.get("filename"),
        "size": primary_file.get("size", 0),
        "sha1": hashes.get("sha1"),
        "sha512": hashes.get("sha512"),
        "version_id": version.get("id"),
        "version_number": version.get("version_number")
    }


# ============================================================
# СКАЧИВАНИЕ
# ============================================================

def download_resource_pack(
    project_id,
    destination_folder,
    minecraft_version=None,
    filename=None
):
    """
    Скачивает ресурс-пак в указанную папку.

    Возвращает путь к скачанному файлу
    или None при ошибке.
    """

    file_info = get_download_file(
        project_id,
        minecraft_version
    )

    if not file_info:
        print("[RPloader] Подходящий файл не найден.")
        return None

    url = file_info.get("url")

    if not url:
        print("[RPloader] URL файла отсутствует.")
        return None

    os.makedirs(destination_folder, exist_ok=True)

    if filename is None:
        filename = file_info.get("filename")

    if not filename:
        print("[RPloader] Имя файла отсутствует.")
        return None

    destination = os.path.join(
        destination_folder,
        filename
    )

    print(f"[RPloader] Скачивание: {filename}")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MaceLauncher/1.0"
        }
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=60
        ) as response:

            with open(destination, "wb") as file:
                while True:
                    chunk = response.read(1024 * 64)

                    if not chunk:
                        break

                    file.write(chunk)

        print(
            f"[RPloader] Установлен: {destination}"
        )

        return destination

    except urllib.error.HTTPError as e:
        print(
            f"[RPloader] Ошибка скачивания HTTP: "
            f"{e.code}"
        )

    except urllib.error.URLError as e:
        print(
            f"[RPloader] Ошибка соединения: "
            f"{e.reason}"
        )

    except Exception as e:
        print(
            f"[RPloader] Ошибка скачивания: {e}"
        )

    # Если скачивание не удалось,
    # удаляем недокачанный файл.
    if os.path.exists(destination):
        try:
            os.remove(destination)
        except Exception:
            pass

    return None


# ============================================================
# УСТАНОВКА В ПАПКУ КОНКРЕТНОЙ ВЕРСИИ
# ============================================================

def install_resource_pack(
    project_id,
    minecraft_version_folder,
    minecraft_version=None
):
    """
    Устанавливает ресурс-пак непосредственно
    в папку resourcepacks выбранной версии.

    Пример структуры:

    versions/
        MyVersion/
            resourcepacks/
                Faithful.zip
    """

    resourcepacks_folder = os.path.join(
        minecraft_version_folder,
        "resourcepacks"
    )

    return download_resource_pack(
        project_id=project_id,
        destination_folder=resourcepacks_folder,
        minecraft_version=minecraft_version
    )


# ============================================================
# ПРОВЕРКА СОВМЕСТИМОСТИ
# ============================================================

def is_compatible(
    project_id,
    minecraft_version
):
    """
    Проверяет, существует ли версия ресурс-пака
    для указанной версии Minecraft.

    Возвращает True / False.
    """

    versions = get_resource_pack_versions(
        project_id,
        minecraft_version
    )

    return len(versions) > 0


# ============================================================
# ПРОСТОЙ ТЕСТ
# ============================================================

if __name__ == "__main__":

    print("===================================")
    print(" Mace Launcher - RPloader")
    print("===================================")

    version = "1.21.1"

    print(
        f"\nПоиск ресурс-паков для Minecraft {version}..."
    )

    packs = search_resource_packs(
        query="Faithful",
        minecraft_version=version,
        limit=5
    )

    if not packs:
        print("Ресурс-паки не найдены.")
        exit()

    for i, pack in enumerate(packs, 1):

        print(
            f"\n{i}. {pack['name']}"
        )

        print(
            f"   ID: {pack['id']}"
        )

        print(
            f"   Автор: {pack['author']}"
        )

        print(
            f"   Загрузок: {pack['downloads']}"
        )

        print(
            f"   Описание: {pack['description']}"
        )

    print("\nГотово!")