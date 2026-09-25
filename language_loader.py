import os


class LanguageLoader:
    def __init__(self, languages_dir=None, default_lang="en"):
        if languages_dir is None:
            candidate_dirs = ["Languages", "languages"]
            for directory in candidate_dirs:
                if os.path.exists(directory):
                    languages_dir = directory
                    break
            else:
                languages_dir = "Languages"

        self.languages_dir = languages_dir
        self.current_lang = default_lang
        self.translations = {}
        self.load_languages()

    def _normalize_lang_code(self, filename):
        name = os.path.basename(filename)
        if not name.lower().endswith(".txt"):
            return ""

        base = os.path.splitext(name)[0].strip().lower()
        alias_map = {
            "english": "en",
            "russian": "ru",
            "ukrainian": "uk",
        }
        return alias_map.get(base, base)

    def _iter_language_dirs(self):
        dirs = []
        for directory in [self.languages_dir, "Languages", "languages"]:
            if directory and directory not in dirs and os.path.isdir(directory):
                dirs.append(directory)
        if self.languages_dir and self.languages_dir not in dirs:
            dirs.append(self.languages_dir)
        return dirs

    def _ensure_default_files(self):
        for folder in self._iter_language_dirs():
            if not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)

        target_dir = self.languages_dir if os.path.isdir(self.languages_dir) else ("Languages" if os.path.isdir("Languages") else "languages")
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        default_files = {
            "English.txt": "# Default English strings\n# key = value\n",
            "Russian.txt": "# Russian strings\n# key = value\n",
            "Ukrainian.txt": "# Ukrainian strings\n# key = value\n",
        }

        for filename, content in default_files.items():
            path = os.path.join(target_dir, filename)
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as file:
                    file.write(content)

    def load_languages(self):
        """Scans the language folders and loads all .txt files into memory."""
        self.translations = {}
        self._ensure_default_files()

        for directory in self._iter_language_dirs():
            if not os.path.isdir(directory):
                continue
            for filename in sorted(os.listdir(directory)):
                if not filename.lower().endswith(".txt"):
                    continue

                lang_code = self._normalize_lang_code(filename)
                if not lang_code:
                    continue

                file_path = os.path.join(directory, filename)
                lang_data = {}
                try:
                    with open(file_path, "r", encoding="utf-8") as file:
                        for line in file:
                            raw = line.strip()
                            if not raw or raw.startswith("#"):
                                continue
                            if "=" in raw:
                                key, value = raw.split("=", 1)
                                lang_data[key.strip()] = value.strip()
                            elif ":" in raw:
                                key, value = raw.split(":", 1)
                                lang_data[key.strip()] = value.strip()
                except Exception as exc:
                    print(f"Error loading language file {filename}: {exc}")

                if lang_data:
                    self.translations[lang_code] = {**self.translations.get(lang_code, {}), **lang_data}

        if self.current_lang not in self.translations:
            self.current_lang = "en" if "en" in self.translations else next(iter(self.translations), "en")

    def set_language(self, lang_code):
        """Changes the current interface language."""
        normalized = (lang_code or "").strip().lower()
        if not normalized:
            normalized = "en"

        if normalized in self.translations:
            self.current_lang = normalized
            return True

        alias_map = {
            "english": "en",
            "en-us": "en",
            "ru": "ru",
            "uk": "uk",
            "ukrainian": "uk",
            "russian": "ru",
        }
        mapped = alias_map.get(normalized)
        if mapped and mapped in self.translations:
            self.current_lang = mapped
            return True

        return False

    def get(self, key, default=None):
        """Returns the translation for the current language or falls back to English."""
        if key is None:
            return default

        key_text = str(key)
        lang_data = self.translations.get(self.current_lang, {})
        if key_text in lang_data:
            return lang_data[key_text]

        english_data = self.translations.get("en", {})
        if key_text in english_data:
            return english_data[key_text]

        for data in self.translations.values():
            if key_text in data:
                return data[key_text]

        return default if default is not None else key_text


translator = LanguageLoader()