import json
import os
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


class ModLoader:
    def __init__(self):
        pass

    def search(self, query="", loader="", version="", category="", limit=20, offset=0):
        """Живий пошук модів через Modrinth API з правильними facet-фільтрами."""
        try:
            clean_query = (query or "").strip() or "minecraft"
            headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
            params = {"query": clean_query, "limit": max(1, int(limit)), "offset": max(0, int(offset))}

            facets = []
            norm_loader = _normalize_loader_name(loader)
            if norm_loader:
                facets.append([f"categories:{norm_loader}"])
            if version and str(version).lower() not in ["all", ""]:
                facets.append([f"versions:{version}"])
            if category and str(category).lower() not in ["all", ""]:
                facets.append([f"categories:{str(category).lower()}"])

            if facets:
                params["facets"] = json.dumps(facets)

            url = f"{MODRINTH_API_URL}/search?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    return data.get("hits", [])
        except Exception as e:
            print(f"ModLoader search error: {e}")

        return []
