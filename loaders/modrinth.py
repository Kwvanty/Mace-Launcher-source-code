import json
import urllib.parse
import urllib.request


class ModrinthLoader:

  def __init__(self):
    self.base_url = "https://api.modrinth.com/v2"
    self.headers = {
        "User-Agent": (
            "Kuvanty/MaceLauncher/1.0 (Contact: kuvanty.dev@gmail.com;"
            " https://github.com/Kuvanty/MaceLauncher)"
        )
    }

  def search_mods(
      self, query: str, limit: int = 20, loader: str = None, version: str = None
  ):
    """Пошук будь-яких модів через живий Modrinth API з правильним кодуванням фільтрів."""
    try:
      clean_query = query.strip() if query else ""
      params = {"query": clean_query, "limit": limit}

      # Фільтри Modrinth обов'язково передаються як JSON-рядок у форматі facets
      facets = []
      if loader and loader.lower() not in ["all", ""]:
        facets.append([f"loader:{loader.lower()}"])
      if version and version.lower() not in ["all", ""]:
        facets.append([f"versions:{version}"])

      if facets:
        params["facets"] = json.dumps(facets)

      url = f"{self.base_url}/search?{urllib.parse.urlencode(params)}"
      req = urllib.request.Request(url, headers=self.headers)

      with urllib.request.urlopen(req, timeout=10) as response:
        if response.status == 200:
          data = json.loads(response.read().decode("utf-8"))
          return data.get("hits", [])
    except urllib.error.HTTPError as e:
      print(f"Modrinth HTTP Error {e.code}: {e.reason}")
    except Exception as e:
      print(f"Modrinth Search Error: {e}")

    return []

  def get_mod_info(self, project_id: str):
    """Отримання детальної інформації про мод з Modrinth."""
    try:
      url = f"{self.base_url}/project/{project_id}"
      req = urllib.request.Request(url, headers=self.headers)
      with urllib.request.urlopen(req, timeout=10) as response:
        if response.status == 200:
          return json.loads(response.read().decode("utf-8"))
    except Exception as e:
      print(f"Modrinth Project Info Error: {e}")
    return None