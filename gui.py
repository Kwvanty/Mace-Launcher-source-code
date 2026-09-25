# ==========================================
# Sector 0 "Path Fix & Bootstrap"
# ==========================================
import sys
import os

# Принудительно добавляем директорию, где лежит gui.py, в системные пути Python,
# чтобы локальные модули (language_loader, RPloader и др.) всегда находились.
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# ==========================================
# Sector 1 "Imports & App Initialization"
# ==========================================
import io
import json
import math
import colorsys
import multiprocessing
import threading
import time
import traceback
import datetime
import platform
import subprocess
import urllib.request
import urllib.parse
import urllib.error
import ssl
import re
import pygame
from language_loader import LanguageLoader, translator
from launcher_core import (
    get_installed_versions, 
    get_available_minecraft_versions, 
    start_minecraft, 
    is_game_running, 
    stop_minecraft, 
    create_new_version, 
    update_version, 
    update_client, 
    update_jar, 
    backup_version, 
    restore_version_backup, 
    delete_modpack, 
    list_version_backups, 
    MINECRAFT_DIR
)
import RPloader

# Для мониторинга системы (psutil)
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Для окна выбора файла и буфера обмена
try:
    import tkinter as tk
    from tkinter import filedialog
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

# ==========================================
# Sector 2 "Globals, UI Styling & Core Functions"
# ==========================================
DEFAULT_PRESETS = [
    (88, 101, 242),   # Discord Blue
    (46, 204, 113),   # Emerald Green
    (155, 89, 182),   # Amethyst Purple
    (230, 126, 34)    # Pumpkin Orange
]

# Default positions for the editable three-column, two-row module grid.
DEFAULT_LAYOUTS = {
    "left": {"col": 0, "row": 0, "span_w": 1, "span_h": 1},
    "console": {"col": 0, "row": 1, "span_w": 1, "span_h": 1},
    "center": {"col": 1, "row": 0, "span_w": 1, "span_h": 2},
    "right": {"col": 2, "row": 1, "span_w": 1, "span_h": 1},
    "info": {"col": 2, "row": 0, "span_w": 1, "span_h": 1},
}

VERSION_ACTION_LABELS = {
    "update_version": "update version",
    "update_client": "update client",
    "update_jar": "update jar",
    "backup": "create backup",
    "restore": "restore backup",
    "delete": "delete",
}

LAUNCH_ACTION_LABELS = {
    "close": "Close launcher",
    "hide": "Hide launcher",
    "none": "Keep open",
}

BACKGROUNDS_DIR = "backgrounds"
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def ensure_backgrounds_dir():
    if not os.path.exists(BACKGROUNDS_DIR):
        os.makedirs(BACKGROUNDS_DIR, exist_ok=True)
    bg1_path = os.path.join(BACKGROUNDS_DIR, "bg-1.png")
    if not os.path.exists(bg1_path):
        try:
            surf = pygame.Surface((128, 128), pygame.SRCALPHA)
            for i in range(-128, 256, 16):
                pygame.draw.line(surf, (255, 255, 255, 200), (i, 0), (i + 128, 128), 3)
            pygame.image.save(surf, bg1_path)
        except Exception as e:
            print(f"Ошибка создания дефолтного фона: {e}")

# Глобальные переменные
current_theme = "dark"
ui_language = "en"
translator = globals().get("translator", LanguageLoader())
accent_idx = 0
custom_color = (255, 0, 128)
ram_gb = 4
ram_protection = True
launch_action = "close"
auto_backup_enabled = False
always_on_top = False
auto_disable_incompatible_mods = False
check_updates_on_start = True
sound_notifications = True
open_error_log_on_failed_launch = False
auto_start = False
interface_scale = 1.0
skin_path = ""
favorite_versions = []
grid_weights_w = [1.0, 1.5, 1.0]
grid_weights_h = [1.0, 1.2]
detached_modules = []
active_processes = {}
module_layouts = {}
logs = ["[System] Multi-window module system active.", "[System] The ↗ button opens a separate Pygame window."]

# Настройки фона модулей
bg_mode = "preset"           
bg_preset = "none"           
bg_custom_path = ""          
bg_pattern_color = (88, 101, 242) 

versions_scroll_offset = 0
mods_scroll_offset = 0
mod_browser_scroll_offset = 0

frametime_history = []
fps_history = []
game_session_start = None

# Профили никнеймов: {"Ник": "Имя сборки"}.
nickname_profiles = {}
active_nickname = ""
nickname_input_active = False
nickname_input_text = ""
nickname_build_menu_open = False
nickname_build_target = ""


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as file:
            config = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        print(f"Ошибка загрузки конфигурации: {error}")
        return {}

    if not isinstance(config, dict):
        print("Ошибка загрузки конфигурации: корневое значение должно быть объектом")
        return {}
    return config


def save_config(username, last_version):
    config = {
        "username": username,
        "last_version": last_version,
        "theme": current_theme,
        "language": ui_language,
        "accent_idx": accent_idx,
        "custom_color": list(custom_color),
        "ram_gb": ram_gb,
        "ram_protection": ram_protection,
        "launch_action": launch_action,
        "auto_backup_enabled": auto_backup_enabled,
        "always_on_top": always_on_top,
        "auto_disable_incompatible_mods": auto_disable_incompatible_mods,
        "check_updates_on_start": check_updates_on_start,
        "sound_notifications": sound_notifications,
        "open_error_log_on_failed_launch": open_error_log_on_failed_launch,
        "auto_start": auto_start,
        "interface_scale": interface_scale,
        "skin_path": skin_path,
        "favorite_versions": list(favorite_versions),
        "grid_weights_w": grid_weights_w,
        "grid_weights_h": grid_weights_h,
        "detached_modules": detached_modules,
        "module_layouts": module_layouts,
        "bg_mode": bg_mode,
        "bg_preset": bg_preset,
        "bg_custom_path": bg_custom_path,
        "bg_pattern_color": list(bg_pattern_color),
        "nickname_profiles": nickname_profiles if isinstance(globals().get("nickname_profiles"), dict) else {},
        "active_nickname": str(globals().get("active_nickname", username)),
    }
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4, ensure_ascii=False)
    except (OSError, TypeError) as error:
        print(f"Ошибка сохранения конфигурации: {error}")
        return False
    return True


UI_FALLBACK_TRANSLATIONS = {
    "en": {
        "news_tab": "Home", "downloaded_tab": "Downloaded", "mods_tab": "Mods", "upload_photo": "Upload photo",
        "search_mods": "Search mods", "recommended_mods": "Recommended mods", "favorite": "Favorite",
        "unfavorite": "Remove from favorites", "no_downloaded_mods": "No downloaded mods",
        "choose_skin": "Choose skin", "load_skin": "Load skin", "edit_grid": "Customize module grid",
    },
    "ru": {
        "news_tab": "Главная", "downloaded_tab": "Скачаное", "mods_tab": "Моды", "upload_photo": "Загрузить фото",
        "search_mods": "Поиск модов", "recommended_mods": "Рекомендуемые моды", "favorite": "В избранное",
        "unfavorite": "Убрать из избранного", "no_downloaded_mods": "Нет скачанных модов",
        "choose_skin": "Выберите скин", "load_skin": "Загрузить скин", "edit_grid": "Настроить сетку модулей",
    },
    "uk": {
        "news_tab": "Головна", "downloaded_tab": "Завантажене", "mods_tab": "Моди", "upload_photo": "Завантажити фото",
        "search_mods": "Пошук модів", "recommended_mods": "Рекомендовані моди", "favorite": "В обране",
        "unfavorite": "Прибрати з обраного", "no_downloaded_mods": "Немає завантажених модів",
        "choose_skin": "Виберіть скін", "load_skin": "Завантажити скін", "edit_grid": "Налаштувати сітку модулів",
    },
}

def tr(text):
    """Translate UI text while keeping a safe local fallback for newly added labels."""
    key = str(text)
    try:
        value = translator.get(key, key)
    except Exception:
        value = key
    if value == key:
        value = UI_FALLBACK_TRANSLATIONS.get(str(ui_language).lower(), {}).get(key, key)
    return value


def sort_versions_with_favorites(versions):
    """Keep favorited versions at the top without losing the original order."""
    fav = set(str(v) for v in favorite_versions)
    return sorted(list(versions), key=lambda v: (0 if str(v) in fav else 1, list(versions).index(v)))


def is_version_favorite(version):
    return str(version) in {str(v) for v in favorite_versions}


def toggle_version_favorite(version):
    global favorite_versions
    version = str(version or "")
    if not version:
        return False
    if version in favorite_versions:
        favorite_versions = [v for v in favorite_versions if str(v) != version]
        return False
    favorite_versions.append(version)
    return True


def load_star_icon(filled=False, size=(24, 24)):
    """Load images/star.png; tint it yellow when a version is favorited."""
    path = os.path.join("images", "star.png")
    try:
        surf = pygame.image.load(path).convert_alpha()
        surf = pygame.transform.smoothscale(surf, size)
        if filled:
            tinted = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            tinted.fill((255, 215, 45, 255))
            tinted.blit(surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            return tinted
        return surf
    except Exception:
        return None


class LocalizedFont:
    """Pygame font proxy which translates every visible label at render time."""
    def __init__(self, font):
        self._font = font

    def render(self, text, *args, **kwargs):
        return self._font.render(tr(text), *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._font, name)


def set_window_topmost(enabled):
    if platform.system() != "Windows":
        return False
    try:
        import ctypes
        hwnd = pygame.display.get_wm_info()["window"]
        ctypes.windll.user32.SetWindowPos(
            ctypes.c_void_p(hwnd),
            ctypes.c_void_p(-1 if enabled else -2),
            0, 0, 0, 0,
            0x0002 | 0x0001,
        )
        return True
    except Exception:
        return False


def check_for_launcher_updates_now():
    try:
        from update_logic import find_update_archives, get_update_dir, read_manifest, is_version_newer, read_current_version
        update_dir = get_update_dir()
        manifest = read_manifest(update_dir)
        archives = find_update_archives(update_dir)
        if manifest.get("is_update"):
            version = str(manifest.get("version") or manifest.get("new_version") or "0.0.0")
            if is_version_newer(version, read_current_version()):
                return True, f"{version}"
        if archives:
            return True, "archive"
        return False, ""
    except Exception:
        return False, ""


def normalize_console_lines(raw_logs):
    if raw_logs is None:
        return []
    try:
        items = list(raw_logs)
    except Exception:
        try:
            items = list(getattr(raw_logs, "values", lambda: [])())
        except Exception:
            items = []
    return [str(item) for item in items]


def get_live_logs():
    if shared_logs_manager is not None:
        try:
            return normalize_console_lines(shared_logs_manager)
        except Exception:
            pass
    return logs


def add_log(message):
    text = str(message)
    logs.append(text)
    try:
        print(text, flush=True)
    except Exception:
        pass
    if shared_logs_manager is not None:
        try:
            shared_logs_manager.append(text)
        except Exception:
            pass


def get_newest_version_index(versions):
    numeric_versions = [
        (index, tuple(int(part) for part in re.findall(r"\d+", version)))
        for index, version in enumerate(versions)
        if re.search(r"\d", version)
    ]
    if numeric_versions:
        return max(numeric_versions, key=lambda item: item[1])[0]
    return len(versions) - 1 if versions else -1


# Цветовая палитра
ACCENT_COLOR = (88, 101, 242)
TEXT_COLOR = (245, 245, 250)
BG_COLOR = (14, 14, 18)
PANEL_BG = (22, 22, 28)
CARD_BG = (28, 28, 36)
GRAY_TEXT = (140, 145, 160)
INPUT_BG = (18, 18, 24)
BORDER_COLOR = (40, 40, 52)
CONSOLE_TEXT = (150, 230, 150)
ACCENT_HOVER = (113, 126, 255)
DANGER_COLOR = (220, 53, 69)
DANGER_HOVER = (240, 73, 89)
SUCCESS_COLOR = (40, 167, 69)

PICKER_SIZE = 250
picker_surface = None
icons_cache = {}
bg_tiles_cache = {}
bg_scaled_cache = {}

# Expensive visual and hardware data is unchanged between frames. Keep small
# caches so the render loop only redraws it when the underlying input changes.
skin_head_cache = {}
skin_3d_cache = {}
hardware_info_cache = None
hardware_info_cache_time = 0.0
HARDWARE_INFO_REFRESH_SECONDS = 1.0

UI_FONT = "Trebuchet MS"

def get_pintograms_dir():
    for d in [os.path.join("images", "pintograms"), os.path.join("images", "pintogram")]:
        if os.path.exists(d):
            return d
    return os.path.join("images", "pintograms")

PINTOGRAMS_DIR = get_pintograms_dir()

# Шрифты
font_title = None
font_subtitle = None
font_main = None
font_small = None
font_console = None
font_clock = None

loaded_skin_surface = None
shared_logs_manager = None
shared_filter_dict = {}
modrinth_download_status = "Waiting for input..."
mod_icons_cache = {}

mod_browser_page_size = 8
mod_browser_max_cached = 32
mod_browser_api_offset = 0
mod_browser_total_hits = 0
mod_browser_is_loading_more = False
cached_mod_results = []
last_browser_search_query = None
console_scroll_offset = 0
mod_browser_scroll_offset = 0
mod_browser_search_text = ""
mod_browser_search_active = False
mod_browser_scroll_repeat_dir = 0
mod_browser_scroll_repeat_started = 0.0

# Браузер ресурс-паков
rp_browser_page_size = 8
rp_browser_max_cached = 20
rp_browser_api_offset = 0
rp_browser_total_hits = 0
rp_browser_is_loading_more = False
cached_rp_results = []
last_rp_browser_search_query = None
rp_browser_scroll_offset = 0
rp_browser_search_text = ""
rp_browser_search_active = False
rp_browser_scroll_repeat_dir = 0
rp_browser_scroll_repeat_started = 0.0
pending_rp_search_results = []

ui_activity_lock = threading.Lock()
ui_active_operations = set()
pending_browser_search_results = []


def set_ui_activity(name, active):
    """Record long-running work so the main window can show its spinner."""
    with ui_activity_lock:
        if active:
            ui_active_operations.add(name)
        else:
            ui_active_operations.discard(name)


def is_ui_busy():
    with ui_activity_lock:
        return bool(ui_active_operations)


def is_ui_activity_active(name):
    with ui_activity_lock:
        return name in ui_active_operations


def launch_minecraft_background(username, version_id, allocated_ram, log_func):
    try:
        start_minecraft(username, version_id, ram_gb=allocated_ram, log_func=log_func)
    finally:
        set_ui_activity("launch", False)


def draw_activity_spinner(surface, center, ticks, color):
    """Draw a lightweight animated progress indicator without external assets."""
    radius = 10
    segments = 12
    active_segment = (ticks // 70) % segments
    for index in range(segments):
        angle = math.radians(index * (360 / segments) - 90)
        strength = 1.0 - ((active_segment - index) % segments) / segments
        segment_color = tuple(int(70 + (channel - 70) * strength) for channel in color)
        outer = (center[0] + int(math.cos(angle) * radius), center[1] + int(math.sin(angle) * radius))
        inner = (center[0] + int(math.cos(angle) * (radius - 4)), center[1] + int(math.sin(angle) * (radius - 4)))
        pygame.draw.line(surface, segment_color, inner, outer, 3)


def create_mod_icon_placeholder(size=(42, 42), color=None):
    color = color or ACCENT_COLOR
    surf = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(surf, color, (0, 0, size[0], size[1]), border_radius=10)
    pygame.draw.rect(surf, (255, 255, 255, 90), (size[0] // 5, size[1] // 5, size[0] // 2, size[1] // 2), border_radius=6)
    pygame.draw.polygon(surf, (255, 255, 255, 180), [(size[0] // 2, size[1] // 7), (size[0] * 3 // 4, size[1] // 2), (size[0] // 2, size[1] * 6 // 7), (size[0] // 5, size[1] // 2)])
    return surf


def urlopen_modrinth(request, timeout=20):
    """Открывает URL Modrinth с актуальным доверенным набором сертификатов.

    Сначала пробуем certifi (если установлен), затем стандартное хранилище
    сертификатов Python. Проверка TLS/SSL всегда остаётся включённой.
    """
    contexts = []
    try:
        import certifi
        contexts.append(ssl.create_default_context(cafile=certifi.where()))
    except Exception:
        pass

    try:
        contexts.append(ssl.create_default_context())
    except Exception:
        pass

    last_error = None
    for context in contexts:
        try:
            return urllib.request.urlopen(request, timeout=timeout, context=context)
        except urllib.error.URLError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    return urllib.request.urlopen(request, timeout=timeout)


def get_mod_icon_surface(mod_item, size=(42, 42)):
    if not isinstance(mod_item, dict):
        return create_mod_icon_placeholder(size)

    icon_url = (
        mod_item.get("icon_url") or
        mod_item.get("icon") or
        mod_item.get("image_url") or
        mod_item.get("thumbnail")
    )
    cache_key = (icon_url, size)
    if cache_key in mod_icons_cache:
        return mod_icons_cache[cache_key]

    if not icon_url:
        placeholder = create_mod_icon_placeholder(size)
        mod_icons_cache[cache_key] = placeholder
        return placeholder

    try:
        req = urllib.request.Request(icon_url, headers={"User-Agent": "MaceLauncher/1.0"})
        with urlopen_modrinth(req, timeout=8) as response:
            data = response.read()
        if not data:
            raise ValueError("empty icon data")
        image = pygame.image.load(io.BytesIO(data)).convert_alpha()
        image = pygame.transform.smoothscale(image, size)
        mod_icons_cache[cache_key] = image
        return image
    except Exception as exc:
        print(f"Ошибка загрузки иконки мода: {exc}")
        placeholder = create_mod_icon_placeholder(size)
        mod_icons_cache[cache_key] = placeholder
        return placeholder


def open_folder(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        print(f"Помилка відкриття папки {path}: {e}")

def copy_to_clipboard(text):
    if HAS_TKINTER:
        try:
            root = tk.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            root.destroy()
        except:
            pass
    else:
        try:
            pygame.scrap.init()
            pygame.scrap.put(pygame.SCRAP_TEXT, text.encode('utf-8'))
        except:
            pass

def get_browser_filter_value(key, default=None):
    """Безопасно читает фильтры браузера, даже если словарь ещё не инициализирован."""
    try:
        if shared_filter_dict is not None and hasattr(shared_filter_dict, "get"):
            value = shared_filter_dict.get(key, default)
            if value is not None:
                return value
    except Exception:
        pass
    return default


def _resolve_modrinth_mc_version(profile_name):
    """Convert a launcher profile name to its Minecraft version."""
    value = str(profile_name or '').strip()
    if not value or value.lower() in ('all', 'any'):
        return ''
    if re.fullmatch(r'\d+\.\d+(?:\.\d+)?', value):
        return value

    version_dir = os.path.join(MINECRAFT_DIR, 'versions', value)
    candidates = [os.path.join(version_dir, f'{value}.json')]
    try:
        if os.path.isdir(version_dir):
            candidates += [
                os.path.join(version_dir, f)
                for f in os.listdir(version_dir)
                if f.lower().endswith('.json')
            ]
    except OSError:
        pass

    for path in candidates:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for key in ('inheritsFrom', 'minecraft_version', 'minecraftVersion', 'id'):
                candidate = str(data.get(key, '')).strip()
                if re.fullmatch(r'\d+\.\d+(?:\.\d+)?', candidate):
                    return candidate
        except Exception:
            pass

    m = re.search(r'(?<!\d)(\d+\.\d+(?:\.\d+)?)(?!\d)', value)
    return m.group(1) if m else ''


def get_modpack_compatibility(profile_name):
    """Возвращает Minecraft-версию и loader ИМЕННО выбранного мод-пака.

    Пример результата:
        {"minecraft_version": "1.21.1", "loader": "fabric"}

    Источник истины — JSON выбранного профиля. Loader определяется как из
    явных полей, так и из стандартных библиотек Fabric/Forge/NeoForge.
    """
    result = {"minecraft_version": "", "loader": ""}
    value = str(profile_name or "").strip()
    if not value:
        return result

    # Если пользователь передал уже саму Minecraft-версию.
    if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", value):
        result["minecraft_version"] = value
        return result

    version_dir = os.path.join(MINECRAFT_DIR, "versions", value)
    json_candidates = [os.path.join(version_dir, f"{value}.json")]

    try:
        if os.path.isdir(version_dir):
            for filename in os.listdir(version_dir):
                if filename.lower().endswith(".json"):
                    path = os.path.join(version_dir, filename)
                    if path not in json_candidates:
                        json_candidates.append(path)
    except OSError:
        pass

    data = None
    for json_path in json_candidates:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                candidate = json.load(f)
            if isinstance(candidate, dict):
                data = candidate
                break
        except Exception:
            continue

    if not data:
        # Последняя страховка для профилей, в названии которых есть 1.21.1.
        match = re.search(r"(?<!\d)(\d+\.\d+(?:\.\d+)?)(?!\d)", value)
        if match:
            result["minecraft_version"] = match.group(1)
        return result

    # Версия Minecraft.
    for key in ("minecraft_version", "minecraftVersion", "inheritsFrom", "id"):
        candidate = str(data.get(key, "")).strip()
        if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", candidate):
            result["minecraft_version"] = candidate
            break

    # Явные поля loader, если launcher_core их сохраняет.
    for key in ("loader", "mod_loader", "loader_type", "modLoader", "platform"):
        candidate = _normalize_loader_name(str(data.get(key, "")))
        if candidate:
            result["loader"] = candidate
            break

    # Стандартный Minecraft profile.json: ищем loader по координатам библиотек.
    if not result["loader"]:
        libraries = data.get("libraries", []) or []
        for library in libraries:
            name = str(library.get("name", "")).lower()
            if "net.fabricmc:fabric-loader" in name:
                result["loader"] = "fabric"
                break
            if "net.neoforged:neoforge" in name:
                result["loader"] = "neoforge"
                break
            if "net.minecraftforge:forge" in name:
                result["loader"] = "forge"
                break
            if "org.quiltmc:quilt-loader" in name:
                result["loader"] = "quilt"
                break

    # Последняя страховка — определить loader по тексту JSON.
    if not result["loader"]:
        raw = json.dumps(data, ensure_ascii=False).lower()
        if "fabric-loader" in raw or "net.fabricmc" in raw:
            result["loader"] = "fabric"
        elif "net.neoforged" in raw or "neoforge" in raw:
            result["loader"] = "neoforge"
        elif "net.minecraftforge" in raw or "forge" in raw:
            result["loader"] = "forge"
        elif "quilt-loader" in raw or "org.quiltmc" in raw:
            result["loader"] = "quilt"

    return result


def search_modrinth_projects(
    query, mc_version='1.20.1', loader='fabric', sort_asc=True,
    limit=25, offset=0, return_meta=False
):
    """Search Modrinth mods using the current API facets."""
    try:
        clean_query = (query or '').strip()
        real_version = _resolve_modrinth_mc_version(mc_version)
        requested_loader = _normalize_loader_name(loader)

        headers = {
            'User-Agent': 'Kuvanty/MaceLauncher/1.0 (Contact: kuvanty.dev@gmail.com; https://github.com/Kuvanty/MaceLauncher)',
            'Accept': 'application/json',
        }

        params = {
            'limit': max(1, min(int(limit), 100)),
            'offset': max(0, int(offset)),
            'index': 'relevance' if clean_query else 'downloads',
        }
        if clean_query:
            params['query'] = clean_query

        facets = []
        # Modrinth search treats loaders as categories.
        if requested_loader:
            facets.append([f'categories:{requested_loader}'])
        if real_version:
            facets.append([f'versions:{real_version}'])
        facets.append(['project_type:mod'])
        params['facets'] = json.dumps(facets, separators=(',', ':'))

        url = 'https://api.modrinth.com/v2/search?' + urllib.parse.urlencode(params)
        print(f'[ModBrowser] {url}')
        req = urllib.request.Request(url, headers=headers)

        with urlopen_modrinth(req, timeout=12) as response:
            if response.status != 200:
                raise RuntimeError(f'Modrinth HTTP {response.status}')
            data = json.loads(response.read().decode('utf-8'))

        hits = data.get('hits', []) or []
        total = int(data.get('total_hits', len(hits)))
        print(f'[ModBrowser] {len(hits)} results; mc={real_version or "none"}; loader={requested_loader or "all"}')

        # If strict filters return nothing, retry without the version filter.
        if not hits and real_version:
            fallback_facets = []
            if requested_loader:
                fallback_facets.append([f'categories:{requested_loader}'])
            fallback_facets.append(['project_type:mod'])
            params['facets'] = json.dumps(fallback_facets, separators=(',', ':'))
            fallback_url = 'https://api.modrinth.com/v2/search?' + urllib.parse.urlencode(params)
            print(f'[ModBrowser] fallback: {fallback_url}')
            req = urllib.request.Request(fallback_url, headers=headers)
            with urlopen_modrinth(req, timeout=12) as response:
                data = json.loads(response.read().decode('utf-8'))
            hits = data.get('hits', []) or []
            total = int(data.get('total_hits', len(hits)))

        if return_meta:
            return hits, total
        return hits
    except urllib.error.HTTPError as e:
        print(f'[ModBrowser] HTTP error: {e.code} {e.reason}')
    except Exception as e:
        print(f'[ModBrowser] search error: {e}')

    return ([], 0) if return_meta else []


def search_modrinth_projects_async(query_key, query, mc_version, loader, sort_asc, limit, offset, reset):
    """Fetch a browser page away from the Pygame event loop."""
    set_ui_activity("search", True)
    try:
        hits, total = search_modrinth_projects(
            query, mc_version, loader, sort_asc,
            limit=limit, offset=offset, return_meta=True,
        )
        with ui_activity_lock:
            pending_browser_search_results.append({
                "query_key": query_key,
                "hits": hits,
                "total": total,
                "offset": offset,
                "reset": reset,
            })
    finally:
        set_ui_activity("search", False)


def search_resource_packs_async(query_key, query, mc_version, limit, offset, reset):
    """Ищет ресурс-паки в отдельном потоке."""
    set_ui_activity("rp_search", True)
    try:
        packs = RPloader.search_resource_packs(
            query=query,
            minecraft_version=mc_version,
            limit=limit,
            offset=offset,
        )
        with ui_activity_lock:
            pending_rp_search_results.append({
                "query_key": query_key,
                "hits": packs,
                "offset": offset,
                "reset": reset,
            })
    except Exception as exc:
        print(f"[RPBrowser] Ошибка поиска: {exc}")
        with ui_activity_lock:
            pending_rp_search_results.append({
                "query_key": query_key,
                "hits": [],
                "offset": offset,
                "reset": reset,
                "error": str(exc),
            })
    finally:
        set_ui_activity("rp_search", False)


def get_target_resourcepacks_dir(version_name=None):
    """Возвращает стандартную папку resourcepacks Minecraft.

    Minecraft загружает ресурс-паки из .minecraft/resourcepacks, а не из
    папки конкретной версии. Аргумент version_name оставлен для совместимости
    с остальным интерфейсом.
    """
    target = os.path.join(MINECRAFT_DIR, "resourcepacks")
    os.makedirs(target, exist_ok=True)
    return target


def is_resource_pack_installed(project_id, rp_dir, minecraft_version=None):
    """Проверяет наличие файла выбранного ресурс-пака."""
    if not project_id or not rp_dir or not os.path.isdir(rp_dir):
        return False
    try:
        file_info = RPloader.get_download_file(project_id, minecraft_version)
        expected = str(file_info.get("filename", "")).lower() if file_info else ""
        if expected and os.path.isfile(os.path.join(rp_dir, expected)):
            return True
    except Exception as exc:
        print(f"[RPBrowser] Ошибка проверки установки: {exc}")
    return False


def install_resource_pack_for_profile(project_id, profile_name):
    """Скачивает ресурс-пак строго для Minecraft-версии выбранного мод-пака."""
    global modrinth_download_status
    set_ui_activity("rp_download", True)
    try:
        if not profile_name:
            modrinth_download_status = "Ошибка: мод-пак не выбран."
            return False

        compatibility = get_modpack_compatibility(profile_name)
        mc_version = compatibility.get("minecraft_version", "")
        if not mc_version:
            modrinth_download_status = (
                f"Ошибка: не удалось определить Minecraft-версию мод-пака '{profile_name}'."
            )
            return False

        rp_dir = get_target_resourcepacks_dir(profile_name)
        modrinth_download_status = f"Скачивание ресурс-пака для Minecraft {mc_version}..."
        result = RPloader.download_resource_pack(
            project_id=project_id,
            destination_folder=rp_dir,
            minecraft_version=mc_version,
        )

        if result:
            filename = os.path.basename(result)
            modrinth_download_status = f"Ресурс-пак установлен: {filename} ({mc_version})"
            add_log(
                f"[RPBrowser] Установлен '{filename}' в мод-пак '{profile_name}' "
                f"для Minecraft {mc_version}."
            )
            return True

        modrinth_download_status = f"Не удалось скачать ресурс-пак для {mc_version}."
        return False
    except Exception as exc:
        modrinth_download_status = f"Ошибка ресурс-пака: {exc}"
        print(f"[RPBrowser] Ошибка установки: {exc}")
        return False
    finally:
        set_ui_activity("rp_download", False)


def get_target_mods_dir(version_name=None):
    """Возвращает папку mods именно выбранного мод-пака/профиля.

    В Mace Launcher каждый мод-пак хранит свои моды рядом с профилем:
    .minecraft/versions/<имя_профиля>/mods
    """
    if version_name:
        mods_dir = os.path.join(MINECRAFT_DIR, "versions", str(version_name), "mods")
    else:
        mods_dir = os.path.join(MINECRAFT_DIR, "mods")
    os.makedirs(mods_dir, exist_ok=True)
    return mods_dir


def download_modrinth_project(slug, profile_name, mods_dir, loader=None):
    """Скачивает мод, СТРОГО совместимый с выбранным мод-паком.

    profile_name — имя папки выбранного мод-пака, а не фильтр браузера.
    Сначала читаем JSON профиля и определяем Minecraft + loader, затем
    запрашиваем у Modrinth только подходящие версии проекта.
    """
    global modrinth_download_status

    set_ui_activity("download", True)
    modrinth_download_status = f"Проверка совместимости '{slug}'..."

    try:
        if not profile_name:
            modrinth_download_status = "Ошибка: мод-пак не выбран."
            return False

        compatibility = get_modpack_compatibility(profile_name)
        pack_version = compatibility.get("minecraft_version", "")
        pack_loader = compatibility.get("loader", "")

        # loader из аргумента НЕ является источником истины. Он используется
        # только как дополнительная информация, если профиль действительно
        # не содержит loader.
        if not pack_loader and loader:
            pack_loader = _normalize_loader_name(loader)

        if not pack_version:
            modrinth_download_status = (
                f"Ошибка: не удалось определить Minecraft-версию мод-пака '{profile_name}'."
            )
            print(f"[ModBrowser] Compatibility failed: profile={profile_name!r}")
            return False

        if not pack_loader:
            modrinth_download_status = (
                f"Ошибка: не удалось определить загрузчик мод-пака '{profile_name}'."
            )
            print(f"[ModBrowser] Loader not found: profile={profile_name!r}")
            return False

        if not mods_dir:
            mods_dir = get_target_mods_dir(profile_name)
        os.makedirs(mods_dir, exist_ok=True)

        # Передаём Modrinth именно параметры выбранного мод-пака.
        params = {
            "loaders": json.dumps([pack_loader]),
            "game_versions": json.dumps([pack_version]),
        }
        url = (
            f"https://api.modrinth.com/v2/project/"
            f"{urllib.parse.quote(str(slug), safe='')}/version?"
            f"{urllib.parse.urlencode(params)}"
        )

        print(
            f"[ModBrowser] Установка '{slug}' для мод-пака '{profile_name}': "
            f"Minecraft={pack_version}, loader={pack_loader}"
        )
        print(f"[ModBrowser] {url}")

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Kuvanty/MaceLauncher/1.0 (Contact: kuvanty.dev@gmail.com; https://github.com/Kuvanty/MaceLauncher)",
                "Accept": "application/json",
            },
        )

        with urlopen_modrinth(req, timeout=20) as response:
            if response.status != 200:
                raise RuntimeError(f"Modrinth HTTP {response.status}")
            data = json.loads(response.read().decode("utf-8"))

        if not isinstance(data, list):
            modrinth_download_status = f"Ошибка: Modrinth вернул неверный ответ для {slug}."
            return False

        # Дополнительная локальная проверка. Никаких fallback на data[0]!
        compatible = []
        for version_data in data:
            game_versions = {
                str(v) for v in (version_data.get("game_versions", []) or [])
            }
            loaders = {
                _normalize_loader_name(str(v))
                for v in (version_data.get("loaders", []) or [])
            }

            if pack_version not in game_versions:
                continue
            if pack_loader not in loaders:
                continue
            if not version_data.get("files"):
                continue

            compatible.append(version_data)

        if not compatible:
            modrinth_download_status = (
                f"Для {slug} нет версии под {pack_version} + {pack_loader}."
            )
            print(
                f"[ModBrowser] Нет совместимой версии: "
                f"{slug}, {pack_version}, {pack_loader}"
            )
            return False

        # Modrinth обычно отдаёт новые версии первыми. Дополнительно сортируем
        # по дате публикации, чтобы выбор был предсказуемым.
        compatible.sort(
            key=lambda item: str(
                item.get("date_published") or item.get("date_created") or ""
            ),
            reverse=True,
        )
        chosen_version = compatible[0]

        files = chosen_version.get("files", []) or []
        file_info = next(
            (entry for entry in files if entry.get("primary") is True),
            files[0] if files else None,
        )

        if not file_info:
            modrinth_download_status = "Ошибка: у совместимой версии нет файла."
            return False

        file_url = file_info.get("url")
        file_name = file_info.get("filename") or f"{slug}.jar"

        if not file_url:
            modrinth_download_status = "Ошибка: у файла Modrinth нет URL."
            return False
        if not file_name.lower().endswith(".jar"):
            modrinth_download_status = f"Ошибка: найденный файл не JAR: {file_name}"
            return False

        modrinth_download_status = (
            f"Скачивание {file_name} ({pack_version}, {pack_loader})..."
        )

        dest = os.path.join(mods_dir, file_name)
        req_file = urllib.request.Request(
            file_url,
            headers={"User-Agent": "MaceLauncher/1.0"},
        )

        temp_dest = dest + ".download"
        try:
            with urlopen_modrinth(req_file, timeout=30) as response, open(temp_dest, "wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
            if not os.path.isfile(temp_dest):
                raise IOError(f"Файл не создан после скачивания: {temp_dest}")
            file_size = os.path.getsize(temp_dest)
            if file_size <= 0:
                raise IOError(f"Скачанный файл пустой: {temp_dest}")
            os.replace(temp_dest, dest)
        finally:
            if os.path.exists(temp_dest):
                try:
                    os.remove(temp_dest)
                except OSError:
                    pass

        if not os.path.isfile(dest):
            raise IOError(f"Modrinth сообщил об успехе, но JAR отсутствует: {dest}")
        final_size = os.path.getsize(dest)
        if final_size <= 0:
            raise IOError(f"JAR-файл пустой: {dest}")

        modrinth_download_status = (
            f"Успешно установлено: {file_name}! "
            f"({pack_version}, {pack_loader})"
        )
        print(f"[ModBrowser] Installed: {dest} ({final_size} bytes)")
        add_log(f"[ModBrowser] Файл установлен: {dest}")
        return True

    except urllib.error.HTTPError as e:
        if e.code == 404:
            modrinth_download_status = f"Ошибка: Мод '{slug}' не найден на Modrinth."
        else:
            modrinth_download_status = f"HTTP Ошибка Modrinth: {e.code}"
        print(f"[ModBrowser] HTTP error: {e.code} {e.reason}")
        return False
    except Exception as e:
        modrinth_download_status = f"Ошибка скачивания: {e}"
        print(f"[ModBrowser] Download error: {e}")
        return False
    finally:
        set_ui_activity("download", False)


def get_modrinth_project_info(slug):
    if not slug:
        return {}
    try:
        req = urllib.request.Request(
            f"https://api.modrinth.com/v2/project/{slug}",
            headers={"User-Agent": "MaceLauncher/1.0"},
        )
        with urlopen_modrinth(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}


def get_modrinth_project_versions(slug):
    if not slug:
        return []
    try:
        req = urllib.request.Request(
            f"https://api.modrinth.com/v2/project/{slug}/version",
            headers={"User-Agent": "MaceLauncher/1.0"},
        )
        with urlopen_modrinth(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _normalize_loader_name(loader):
    val = (loader or "").strip().lower()
    if not val or val in ["all", "any"]:
        return ""
    aliases = {
        "curseforge": "forge",
        "forge": "forge",
        "neoforge": "neoforge",
        "fabric": "fabric",
        "quilt": "quilt",
    }
    return aliases.get(val, val)


def _loader_matches(item_loaders, requested_loader):
    if not requested_loader:
        return True
    requested = _normalize_loader_name(requested_loader)
    if not requested:
        return True
    actual = {_normalize_loader_name(str(item)) for item in (item_loaders or []) if str(item).strip()}
    return requested in actual


def _version_matches_loader(version_data, requested_loader):
    if not requested_loader:
        return True
    requested = _normalize_loader_name(requested_loader)
    if not requested:
        return True

    loaders = version_data.get("loaders") or version_data.get("loaders_raw") or []
    if not loaders:
        return False

    item_loaders = {_normalize_loader_name(str(x)) for x in loaders if str(x).strip()}
    return requested in item_loaders


def _select_loader_compatible_version(project_versions, mc_version, loader):
    versions = project_versions or []
    if not versions:
        return None

    requested_loader = _normalize_loader_name(loader)
    best = []
    fallback = []

    for item in versions:
        game_versions = item.get("game_versions", []) or []
        if mc_version and str(mc_version) not in [str(v) for v in game_versions]:
            continue

        if requested_loader:
            if not _version_matches_loader(item, requested_loader):
                continue

        if item.get("files"):
            best.append(item)
        else:
            fallback.append(item)

    if best:
        return best[0]
    if fallback:
        return fallback[0]
    return versions[0]


def get_latest_compatible_mod_version(slug, mc_version, loader):
    versions = get_modrinth_project_versions(slug)
    if not versions:
        return None
    return _select_loader_compatible_version(versions, mc_version, loader)


def is_mod_installed_by_slug(slug, mods_dir):
    if not slug or not os.path.exists(mods_dir):
        return False
    slug_clean = str(slug).lower().replace("-", "").replace("_", "")
    for name in os.listdir(mods_dir):
        lower = name.lower().replace("-", "").replace("_", "")
        if slug_clean in lower:
            return True
    return False


def install_selected_mod_version(slug, mc_version, loader, mods_dir, version_info=None):
    if not slug or not mods_dir:
        return False, "Не указаны данные мода"
    try:
        target_version = version_info or get_latest_compatible_mod_version(slug, mc_version, loader)
        if not target_version:
            return False, "Не удалось найти совместимую версию"
        files = target_version.get("files", [])
        if not files:
            return False, "У версии нет файлов для скачивания"

        file_info = None
        for maybe in files:
            if maybe.get("primary") is True:
                file_info = maybe
                break
        if file_info is None:
            file_info = files[0]

        url = file_info.get("url")
        file_name = file_info.get("filename") or f"{slug}.jar"
        os.makedirs(mods_dir, exist_ok=True)
        dest = os.path.join(mods_dir, file_name)
        req = urllib.request.Request(url, headers={"User-Agent": "MaceLauncher/1.0"})
        with urlopen_modrinth(req, timeout=30) as response, open(dest, "wb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        return True, file_name
    except Exception as exc:
        return False, str(exc)


def get_total_system_ram():
    if HAS_PSUTIL:
        try:
            return max(4, round(psutil.virtual_memory().total / (1024 ** 3)))
        except Exception:
            pass
    return 8

def get_max_allowed_ram():
    total = get_total_system_ram()
    if ram_protection:
        return max(2, total - 1)
    return total

def build_picker_surface():
    global picker_surface
    picker_surface = pygame.Surface((PICKER_SIZE, PICKER_SIZE))
    arr = pygame.PixelArray(picker_surface)
    for x in range(PICKER_SIZE):
        hue = x / PICKER_SIZE
        for y in range(PICKER_SIZE):
            sat = 1.0 - (y / PICKER_SIZE)
            r, g, b = colorsys.hsv_to_rgb(hue, sat, 1.0)
            arr[x, y] = (int(r * 255), int(g * 255), int(b * 255))
    del arr

def load_and_recolor_icon(filename: str, target_color: tuple, size=(20, 20)):
    icon_path = os.path.join(PINTOGRAMS_DIR, filename)
    if not os.path.exists(icon_path):
        return None
    try:
        surface = pygame.image.load(icon_path).convert_alpha()
        surface = pygame.transform.scale(surface, size)
        recolored = surface.copy()
        
        with pygame.PixelArray(recolored) as px_arr:
            r, g, b = target_color
            for x in range(recolored.get_width()):
                for y in range(recolored.get_height()):
                    color = recolored.unmap_rgb(px_arr[x, y])
                    if color.a > 0:
                        px_arr[x, y] = (r, g, b, color.a)
        return recolored
    except Exception as e:
        print(f"Ошибка пиктограммы {filename}: {e}")
        return None

def reload_all_pintograms():
    global icons_cache
    icons_cache["optpin"] = load_and_recolor_icon("optpin.png", TEXT_COLOR, (20, 20))
    icons_cache["settings"] = load_and_recolor_icon("settings.png", TEXT_COLOR, (20, 20))
    icons_cache["folder"] = load_and_recolor_icon("folder.png", TEXT_COLOR, (20, 20))
    icons_cache["pancil"] = load_and_recolor_icon("pancil.png", TEXT_COLOR, (20, 20))
    icons_cache["pencil"] = load_and_recolor_icon("pencil.png", TEXT_COLOR, (20, 20))
    icons_cache["openwindow"] = load_and_recolor_icon("openwindow.png", TEXT_COLOR, (16, 16))
    icons_cache["copy"] = load_and_recolor_icon("copy.png", TEXT_COLOR, (20, 20))
    icons_cache["editpin"] = load_and_recolor_icon("editpin.png", TEXT_COLOR, (20, 20))
    icons_cache["update"] = load_and_recolor_icon("Up.png", TEXT_COLOR, (22, 22))
    icons_cache["networks"] = load_and_recolor_icon("Networks.png", TEXT_COLOR, (22, 22))

def get_background_tile(mode, preset_name, custom_path, tint_color):
    cache_key = (mode, preset_name, custom_path, tint_color)
    if cache_key in bg_tiles_cache:
        return bg_tiles_cache[cache_key]

    if mode == "none":
        return None

    img_path = None
    if mode == "preset":
        file_name = preset_name if preset_name.endswith(".png") else f"{preset_name}.png"
        img_path = os.path.join(BACKGROUNDS_DIR, file_name)
    elif mode == "custom":
        img_path = custom_path

    if not img_path or not os.path.exists(img_path):
        return None

    try:
        raw_surf = pygame.image.load(img_path).convert_alpha()
        if mode == "preset":
            recolored = raw_surf.copy()
            tr, tg, tb = tint_color
            with pygame.PixelArray(recolored) as px:
                for x in range(recolored.get_width()):
                    for y in range(recolored.get_height()):
                        c = recolored.unmap_rgb(px[x, y])
                        if c.a > 0:
                            avg = (c.r + c.g + c.b) // 3
                            nr = int((avg / 255.0) * tr)
                            ng = int((avg / 255.0) * tg)
                            nb = int((avg / 255.0) * tb)
                            alpha = int(c.a * 0.35)  
                            px[x, y] = (nr, ng, nb, alpha)
            bg_tiles_cache[cache_key] = recolored
            return recolored
        else:
            bg_tiles_cache[cache_key] = raw_surf
            return raw_surf
    except Exception as e:
        print(f"Ошибка загрузки фона модуля {img_path}: {e}")
        return None

def draw_module_background(surface, rect, mode, preset_name, custom_path, tint_color):
    """Отрисовка фона СТРОГО внутри прямоугольника модуля (Full screen bounds)"""
    if mode == "none":
        return

    tile = get_background_tile(mode, preset_name, custom_path, tint_color)
    if not tile:
        return

    old_clip = surface.get_clip()
    surface.set_clip(rect)

    if mode == "preset":
        tw, th = tile.get_width(), tile.get_height()
        if tw > 0 and th > 0:
            for x in range(rect.x, rect.right, tw):
                for y in range(rect.y, rect.bottom, th):
                    surface.blit(tile, (x, y))
    elif mode == "custom":
        screen_w, screen_h = surface.get_size()
        cache_key = (id(tile), screen_w, screen_h)
        scaled = bg_scaled_cache.get(cache_key)
        if scaled is None:
            scaled = pygame.transform.smoothscale(tile, (screen_w, screen_h))
            scaled.set_alpha(90)
            bg_scaled_cache[cache_key] = scaled
        surface.blit(scaled, (rect.x, rect.y), area=rect)

    surface.set_clip(old_clip)

def update_theme_colors():
    global BG_COLOR, CARD_BG, TEXT_COLOR, GRAY_TEXT, INPUT_BG, BORDER_COLOR, CONSOLE_TEXT
    global ACCENT_COLOR, ACCENT_HOVER, DANGER_COLOR, DANGER_HOVER, PANEL_BG, SUCCESS_COLOR
    
    if accent_idx < len(DEFAULT_PRESETS):
        ACCENT_COLOR = DEFAULT_PRESETS[accent_idx]
    else:
        ACCENT_COLOR = custom_color

    ACCENT_HOVER = (
        min(255, ACCENT_COLOR[0] + 25),
        min(255, ACCENT_COLOR[1] + 25),
        min(255, ACCENT_COLOR[2] + 25)
    )
    
    DANGER_COLOR = (220, 53, 69)
    DANGER_HOVER = (240, 73, 89)
    SUCCESS_COLOR = (40, 167, 69)

    if current_theme == "dark":
        BG_COLOR = (14, 14, 18)
        PANEL_BG = (22, 22, 28)
        CARD_BG = (28, 28, 36)
        TEXT_COLOR = (245, 245, 250)
        GRAY_TEXT = (140, 145, 160)
        INPUT_BG = (18, 18, 24)
        BORDER_COLOR = (40, 40, 52)
        CONSOLE_TEXT = (150, 230, 150)
    else:
        BG_COLOR = (235, 238, 242)
        PANEL_BG = (255, 255, 255)
        CARD_BG = (245, 247, 250)
        TEXT_COLOR = (20, 20, 25)
        GRAY_TEXT = (110, 115, 130)
        INPUT_BG = (230, 233, 240)
        BORDER_COLOR = (210, 215, 225)
        CONSOLE_TEXT = (30, 130, 30)

    reload_all_pintograms()

def init_fonts():
    global font_title, font_subtitle, font_main, font_small, font_console, font_clock
    scale = float(interface_scale if interface_scale else 1.0)
    sys_font = UI_FONT if UI_FONT.lower().replace(" ", "") in pygame.font.get_fonts() else "Verdana"
    font_title = LocalizedFont(pygame.font.SysFont(sys_font, max(10, int(22 * scale)), bold=True))
    font_subtitle = LocalizedFont(pygame.font.SysFont(sys_font, max(10, int(16 * scale)), bold=True))
    font_main = LocalizedFont(pygame.font.SysFont(sys_font, max(10, int(14 * scale)), bold=True))
    font_small = LocalizedFont(pygame.font.SysFont(sys_font, max(10, int(12 * scale)), bold=True))
    font_console = LocalizedFont(pygame.font.SysFont("Consolas", max(9, int(11 * scale)), bold=False))
    font_clock = LocalizedFont(pygame.font.SysFont(sys_font, max(12, int(24 * scale)), bold=True))


def reopen_pygame_window(width, height):
    """Restore the launcher window after the configured close-on-launch mode."""
    global screen, clock
    pygame.init()
    screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
    pygame.display.set_caption("Mace Launcher")
    init_fonts()
    clock = pygame.time.Clock()

def load_skin_file(path):
    global loaded_skin_surface
    skin_head_cache.clear()
    skin_3d_cache.clear()
    if path and os.path.exists(path):
        try:
            loaded_skin_surface = pygame.image.load(path).convert_alpha()
            return True
        except Exception as e:
            print(f"Ошибка загрузки скина: {e}")
    loaded_skin_surface = None
    return False


def _pick_file_dialog(title, initial_dir=None, filetypes=None):
    if not HAS_TKINTER:
        print("Tkinter недоступен: выбор файла невозможен.")
        return ""

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            root.lift()
            root.focus_force()
        except Exception:
            pass

        start_dir = initial_dir or os.getcwd()
        if not os.path.exists(start_dir):
            start_dir = os.getcwd()

        selected = filedialog.askopenfilename(
            title=title,
            initialdir=start_dir,
            parent=root,
            filetypes=filetypes or [
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                ("All files", "*.*"),
            ],
        )
        return selected or ""
    except Exception as exc:
        print(f"Ошибка выбора файла: {exc}")
        return ""
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass




def select_skin_dialog():
    global skin_path
    selected = _pick_file_dialog(
        tr("choose_skin"),
        initial_dir=os.path.dirname(skin_path) if skin_path and os.path.exists(os.path.dirname(skin_path)) else os.getcwd(),
        filetypes=[
            ("PNG / JPG / BMP / GIF / WEBP", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
            ("All files", "*.*"),
        ],
    )
    if not selected:
        return ""

    try:
        probe = pygame.image.load(selected)
        if probe.get_width() < 64 or probe.get_height() < 32:
            print("Ошибка: файл слишком маленький для скина Minecraft.")
            return ""
    except Exception as exc:
        print(f"Ошибка проверки скина: {exc}")
        return ""
    skin_path = selected
    load_skin_file(skin_path)
    try:
        save_config(globals().get("username", ""), globals().get("cur_ver", ""))
    except Exception:
        pass
    return skin_path


def select_custom_bg_dialog():
    global bg_custom_path
    selected = _pick_file_dialog(
        tr("choose_background"),
        initial_dir=os.path.dirname(bg_custom_path) if bg_custom_path and os.path.exists(os.path.dirname(bg_custom_path)) else BACKGROUNDS_DIR,
        filetypes=[
            ("PNG / JPG / BMP / GIF / WEBP", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
            ("All files", "*.*"),
        ],
    )
    if not selected:
        return ""

    bg_custom_path = selected
    return selected


def render_skin_head(size=36):
    cache_key = (id(loaded_skin_surface), size)
    cached = skin_head_cache.get(cache_key)
    if cached is not None:
        return cached

    head_surf = pygame.Surface((size, size), pygame.SRCALPHA)
    
    if loaded_skin_surface:
        base_head = loaded_skin_surface.subsurface(pygame.Rect(8, 8, 8, 8))
        base_scaled = pygame.transform.scale(base_head, (size, size))
        head_surf.blit(base_scaled, (0, 0))

        try:
            hat_head = loaded_skin_surface.subsurface(pygame.Rect(40, 8, 8, 8))
            hat_scaled = pygame.transform.scale(hat_head, (size, size))
            head_surf.blit(hat_scaled, (0, 0))
        except Exception:
            pass
    else:
        pygame.draw.rect(head_surf, (190, 125, 90), (0, 0, size, size), border_radius=4)
        pygame.draw.rect(head_surf, (80, 50, 30), (0, 0, size, size // 3))
        pygame.draw.rect(head_surf, (255, 255, 255), (size // 6, size // 2, size // 5, size // 6))
        pygame.draw.rect(head_surf, (255, 255, 255), (size - size // 3, size // 2, size // 5, size // 6))
    skin_head_cache[cache_key] = head_surf
    return head_surf

def draw_3d_box(surface, texture, src_rect, dest_rect, is_outer=False):
    if not texture:
        pygame.draw.rect(surface, ACCENT_COLOR, dest_rect, border_radius=3)
        pygame.draw.rect(surface, TEXT_COLOR, dest_rect, width=1, border_radius=3)
        return

    x, y, w, h = dest_rect
    if is_outer:
        expand = max(1, int(w * 0.08))
        x -= expand
        y -= expand
        w += expand * 2
        h += expand * 2

    sx, sy, sw, sh = src_rect
    try:
        part = texture.subsurface(pygame.Rect(sx, sy, sw, sh))
        scaled = pygame.transform.scale(part, (max(1, w), max(1, h)))
        if is_outer:
            scaled.set_alpha(230)
        surface.blit(scaled, (x, y))
    except Exception:
        pass

def render_full_3d_skin(target_rect):
    cache_key = (id(loaded_skin_surface), target_rect.width, target_rect.height)
    cached = skin_3d_cache.get(cache_key)
    if cached is not None:
        return cached

    surf = pygame.Surface((target_rect.width, target_rect.height), pygame.SRCALPHA)
    cx = target_rect.width // 2
    cy = target_rect.height // 2 - 10
    scale = min(target_rect.width / 140, target_rect.height / 240)

    hw, hh = int(32 * scale), int(32 * scale)
    bw, bh = int(32 * scale), int(48 * scale)
    aw, ah = int(16 * scale), int(48 * scale)
    lw, lh = int(16 * scale), int(48 * scale)

    head_r = pygame.Rect(cx - hw // 2, cy - int(80 * scale), hw, hh)
    body_r = pygame.Rect(cx - bw // 2, head_r.bottom, bw, bh)
    l_arm_r = pygame.Rect(body_r.left - aw - 2, body_r.y, aw, ah)
    r_arm_r = pygame.Rect(body_r.right + 2, body_r.y, aw, ah)
    l_leg_r = pygame.Rect(body_r.left, body_r.bottom + 2, lw, lh)
    r_leg_r = pygame.Rect(body_r.right - lw, body_r.bottom + 2, lw, lh)

    draw_3d_box(surf, loaded_skin_surface, (8, 8, 8, 8), head_r)        
    draw_3d_box(surf, loaded_skin_surface, (20, 20, 8, 12), body_r)     
    draw_3d_box(surf, loaded_skin_surface, (44, 20, 4, 12), l_arm_r)    
    draw_3d_box(surf, loaded_skin_surface, (36, 52, 4, 12), r_arm_r)    
    draw_3d_box(surf, loaded_skin_surface, (4, 20, 4, 12), l_leg_r)     
    draw_3d_box(surf, loaded_skin_surface, (20, 52, 4, 12), r_leg_r)    

    if loaded_skin_surface and loaded_skin_surface.get_height() >= 64:
        draw_3d_box(surf, loaded_skin_surface, (40, 8, 8, 8), head_r, is_outer=True)    
        draw_3d_box(surf, loaded_skin_surface, (20, 36, 8, 12), body_r, is_outer=True)  
        draw_3d_box(surf, loaded_skin_surface, (48, 36, 4, 12), l_arm_r, is_outer=True) 
        draw_3d_box(surf, loaded_skin_surface, (52, 52, 4, 12), r_arm_r, is_outer=True) 
        draw_3d_box(surf, loaded_skin_surface, (4, 36, 4, 12), l_leg_r, is_outer=True)  
        draw_3d_box(surf, loaded_skin_surface, (4, 52, 4, 12), r_leg_r, is_outer=True)  
    skin_3d_cache[cache_key] = surf
    return surf

def get_hardware_info():
    global hardware_info_cache, hardware_info_cache_time
    now = time.monotonic()
    if hardware_info_cache is not None and now - hardware_info_cache_time < HARDWARE_INFO_REFRESH_SECONDS:
        return hardware_info_cache

    cpu_name = platform.processor() or "CPU"
    if platform.system() == "Windows":
        try:
            import wmi
            w = wmi.WMI()
            cpus = w.Win32_Processor()
            if cpus and cpus[0].Name:
                cpu_name = cpus[0].Name.strip()
        except Exception:
            pass

    cpu_usage = 0
    cpu_temp = "Н/Д"
    if HAS_PSUTIL:
        try:
            cpu_usage = int(psutil.cpu_percent())
            temps = psutil.sensors_temperatures() if hasattr(psutil, 'sensors_temperatures') else {}
            if temps:
                for name, entries in temps.items():
                    if entries:
                        cpu_temp = f"{int(entries[0].current)}°C"
                        break
        except Exception:
            pass

    gpu_name = "GPU"
    gpu_usage = 0
    gpu_temp = "Н/Д"
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            gpu = gpus[0]
            gpu_name = gpu.name.strip()
            gpu_usage = int(gpu.load * 100)
            gpu_temp = f"{int(gpu.temperature)}°C"
    except Exception:
        pass

    ram_usage_pct = 0
    ram_model = "DDR"
    ram_count = 1
    ram_temp = "Н/Д"
    
    if HAS_PSUTIL:
        try:
            vm = psutil.virtual_memory()
            ram_usage_pct = int(vm.percent)
        except Exception:
            pass

    if platform.system() == "Windows":
        try:
            import wmi
            w = wmi.WMI()
            mems = w.Win32_PhysicalMemory()
            if mems:
                ram_count = len(mems)
                mfg = getattr(mems[0], "Manufacturer", "").strip()
                part = getattr(mems[0], "PartNumber", "").strip()
                full_name = f"{mfg} {part}".strip()
                if full_name:
                    ram_model = full_name
        except Exception:
            pass

    hardware_info_cache = {
        "cpu_name": cpu_name, "cpu_usage": cpu_usage, "cpu_temp": cpu_temp,
        "gpu_name": gpu_name, "gpu_usage": gpu_usage, "gpu_temp": gpu_temp,
        "ram_model": ram_model, "ram_count": ram_count, "ram_usage": ram_usage_pct, "ram_temp": ram_temp
    }
    hardware_info_cache_time = now
    return hardware_info_cache

def draw_info_module_content(surface, rect, cur_fps, game_running=None):
    if rect.height < 150:
        header_surf = font_small.render(tr("system_time"), True, GRAY_TEXT)
        surface.blit(header_surf, (rect.x + 10, rect.y + 6))
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        time_surf = font_subtitle.render(now_str, True, ACCENT_COLOR)
        surface.blit(time_surf, (rect.x + 10, rect.y + 22))
        fps_text = f"FPS: {int(cur_fps)} | RAM load: {get_hardware_info()['ram_usage']}%"
        surface.blit(font_small.render(fps_text, True, TEXT_COLOR), (rect.x + 10, rect.y + 48))
        return

    header_surf = font_small.render(tr("system_time"), True, GRAY_TEXT)
    surface.blit(header_surf, (rect.x + 12, rect.y + 8))

    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    time_surf = font_clock.render(now_str, True, ACCENT_COLOR)
    surface.blit(time_surf, (rect.x + 12, rect.y + 24))

    global game_session_start
    if game_running is None:
        game_running = is_game_running()
    if game_running:
        if game_session_start is None:
            game_session_start = time.time()
        elapsed = int(time.time() - game_session_start)
        hrs = elapsed // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        session_str = f"{tr('session_label')}: {hrs:02d}:{mins:02d}:{secs:02d}"
        session_color = SUCCESS_COLOR
    else:
        game_session_start = None

        session_str = f"{tr('session_label')}: {tr('not_in_game')}"
        session_color = GRAY_TEXT

    sess_surf = font_small.render(session_str, True, session_color)
    surface.blit(sess_surf, (rect.x + 12, rect.y + 54))

    avg_fps = int(sum(fps_history) / len(fps_history)) if fps_history else int(cur_fps)
    min_fps = int(min(fps_history)) if fps_history else int(cur_fps)
    max_fps = int(max(fps_history)) if fps_history else int(cur_fps)
    tps_val = 20.0 if game_running else 0.0

    fps_text = f"FPS: {int(cur_fps)} (Avg:{avg_fps} Min:{min_fps} Max:{max_fps}) | TPS: {tps_val:.1f}"
    fps_surf = font_small.render(fps_text, True, TEXT_COLOR)
    surface.blit(fps_surf, (rect.x + 12, rect.y + 72))

    sep_y = rect.y + 92
    if sep_y + 10 < rect.bottom:
        pygame.draw.line(surface, BORDER_COLOR, (rect.x + 10, sep_y), (rect.right - 10, sep_y), 1)

    hw_info = get_hardware_info()

    def get_status_data(usage):
        if usage < 25:
            return tr("status_good"), (40, 167, 69)
        elif usage < 50:
            return tr("status_normal"), (173, 255, 47)
        elif usage < 60:
            return tr("status_medium"), (255, 193, 7)
        elif usage < 80:
            return tr("status_heavy"), (253, 126, 20)
        else:
            return tr("status_very_heavy"), (220, 53, 69)

    cpu_usage = hw_info["cpu_usage"]
    gpu_usage = hw_info["gpu_usage"]
    ram_usage = hw_info["ram_usage"]

    cpu_status_txt, cpu_status_col = get_status_data(cpu_usage)
    gpu_status_txt, gpu_status_col = get_status_data(gpu_usage)
    ram_status_txt, ram_status_col = get_status_data(ram_usage)

    def shorten(text, max_chars=35):
        return text[:max_chars-3] + "..." if len(text) > max_chars else text

    row_y = sep_y + 10

    def draw_vertical_block(tag, name, usage, temp, status_txt, status_col):
        nonlocal row_y
        if row_y + 30 > rect.bottom - 4:
            return

        surface.blit(font_small.render(f"{tag}:", True, ACCENT_COLOR), (rect.x + 12, row_y))
        surface.blit(font_console.render(shorten(name), True, TEXT_COLOR), (rect.x + 48, row_y + 1))
        row_y += 16

        if row_y + 16 > rect.bottom - 4:
            return
        info_str = f"{tr('load')}: {usage}% | {tr('temp')}: {temp}"
        surface.blit(font_console.render(info_str, True, GRAY_TEXT), (rect.x + 12, row_y))

        status_surf = font_console.render(status_txt, True, status_col)
        surface.blit(status_surf, (rect.right - 12 - status_surf.get_width(), row_y))

        row_y += 22

    ram_name = f"{hw_info['ram_model']} ({hw_info['ram_count']} pcs.)"

    draw_vertical_block("CPU", hw_info["cpu_name"], cpu_usage, hw_info["cpu_temp"], cpu_status_txt, cpu_status_col)
    draw_vertical_block("GPU", hw_info["gpu_name"], gpu_usage, hw_info["gpu_temp"], gpu_status_txt, gpu_status_col)
    draw_vertical_block("RAM", ram_name, ram_usage, hw_info["ram_temp"], ram_status_txt, ram_status_col)

# ==========================================
# MOD FILTER PROCESS WINDOW
# ==========================================
def run_mod_filter_process(theme, shared_filter_data, available_versions):
    """Separate Pygame window with mod filters (version, loader, A-Z/Z-A sorting)."""
    try:
        pygame.init()
        sub_screen = pygame.display.set_mode((420, 480))
        pygame.display.set_caption("Mace Launcher - Mod filters")

        init_fonts()
        clock = pygame.time.Clock()

        loaders_list = ["fabric", "forge", "neoforge", "quilt"]

        version_scroll = 0
        loader_scroll = 0

        show_ver_list = False
        show_loader_list = False

        while True:
            bg_c = (14, 14, 18) if theme == "dark" else (235, 238, 242)
            card_c = (28, 28, 36) if theme == "dark" else (245, 247, 250)
            text_c = (245, 245, 250) if theme == "dark" else (20, 20, 25)

            sub_screen.fill(bg_c)

            cur_ver = shared_filter_data.get("version", "1.20.1")
            cur_loader = shared_filter_data.get("loader", "fabric")
            cur_sort_asc = shared_filter_data.get("sort_asc", True)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return
                elif event.type == pygame.MOUSEWHEEL:
                    if show_ver_list:
                        version_scroll = max(0, version_scroll - event.y * 20)
                    elif show_loader_list:
                        loader_scroll = max(0, loader_scroll - event.y * 20)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = event.pos
                    ver_btn_rect = pygame.Rect(30, 80, 360, 40)
                    loader_btn_rect = pygame.Rect(30, 160, 360, 40)
                    sort_btn_rect = pygame.Rect(30, 240, 360, 40)

                    if show_ver_list:
                        v_menu_rect = pygame.Rect(30, 125, 360, 150)
                        if v_menu_rect.collidepoint(pos):
                            clicked_idx = int((pos[1] - v_menu_rect.y + version_scroll) // 35)
                            if 0 <= clicked_idx < len(available_versions):
                                shared_filter_data["version"] = available_versions[clicked_idx]
                                show_ver_list = False
                        else:
                            show_ver_list = False
                    elif show_loader_list:
                        l_menu_rect = pygame.Rect(30, 205, 360, 120)
                        if l_menu_rect.collidepoint(pos):
                            clicked_idx = int((pos[1] - l_menu_rect.y + loader_scroll) // 35)
                            if 0 <= clicked_idx < len(loaders_list):
                                shared_filter_data["loader"] = loaders_list[clicked_idx]
                                show_loader_list = False
                        else:
                            show_loader_list = False
                    else:
                        if ver_btn_rect.collidepoint(pos):
                            show_ver_list = True
                            show_loader_list = False
                        elif loader_btn_rect.collidepoint(pos):
                            show_loader_list = True
                            show_ver_list = False
                        elif sort_btn_rect.collidepoint(pos):
                            shared_filter_data["sort_asc"] = not cur_sort_asc

            sub_screen.blit(font_subtitle.render(tr("mod_filter_title"), True, text_c), (30, 20))

            sub_screen.blit(font_small.render(tr("game_version"), True, GRAY_TEXT), (30, 60))
            ver_btn = pygame.Rect(30, 80, 360, 40)
            pygame.draw.rect(sub_screen, card_c, ver_btn, border_radius=8)
            pygame.draw.rect(sub_screen, BORDER_COLOR, ver_btn, width=1, border_radius=8)
            sub_screen.blit(font_main.render(f"{tr('selected')}: {cur_ver} ({tr('click_to_select')})", True, text_c), (ver_btn.x + 12, ver_btn.y + 11))

            sub_screen.blit(font_small.render(tr("loader"), True, GRAY_TEXT), (30, 140))
            loader_btn = pygame.Rect(30, 160, 360, 40)
            pygame.draw.rect(sub_screen, card_c, loader_btn, border_radius=8)
            pygame.draw.rect(sub_screen, BORDER_COLOR, loader_btn, width=1, border_radius=8)
            sub_screen.blit(font_main.render(f"{tr('loader')}: {cur_loader.upper()}", True, text_c), (loader_btn.x + 12, loader_btn.y + 11))

            sub_screen.blit(font_small.render(tr("sort_order"), True, GRAY_TEXT), (30, 220))
            sort_btn = pygame.Rect(30, 240, 360, 40)
            pygame.draw.rect(sub_screen, card_c, sort_btn, border_radius=8)
            pygame.draw.rect(sub_screen, BORDER_COLOR, sort_btn, width=1, border_radius=8)
            sort_text = tr("sort_a_to_z") if cur_sort_asc else tr("sort_z_to_a")
            sub_screen.blit(font_main.render(f"{tr('sort')}: {sort_text}", True, text_c), (sort_btn.x + 12, sort_btn.y + 11))

            bottom_rect = pygame.Rect(30, 410, 360, 50)
            pygame.draw.rect(sub_screen, PANEL_BG, bottom_rect, border_radius=8)
            pygame.draw.rect(sub_screen, ACCENT_COLOR, bottom_rect, width=1, border_radius=8)
            target_str = f"{tr('mods_will_install_on_version')}: {cur_ver}"
            sub_screen.blit(font_small.render(target_str, True, SUCCESS_COLOR), (bottom_rect.x + 12, bottom_rect.centery - 8))

            if show_ver_list:
                v_menu = pygame.Rect(30, 125, 360, 160)
                pygame.draw.rect(sub_screen, PANEL_BG, v_menu, border_radius=8)
                pygame.draw.rect(sub_screen, ACCENT_COLOR, v_menu, width=1, border_radius=8)

                old_clip = sub_screen.get_clip()
                sub_screen.set_clip(v_menu)
                for idx, v in enumerate(available_versions):
                    item_y = v_menu.y + 5 + idx * 35 - version_scroll
                    sub_screen.blit(font_main.render(v, True, text_c), (v_menu.x + 15, item_y + 8))
                sub_screen.set_clip(old_clip)

            if show_loader_list:
                l_menu = pygame.Rect(30, 205, 360, 120)
                pygame.draw.rect(sub_screen, PANEL_BG, l_menu, border_radius=8)
                pygame.draw.rect(sub_screen, ACCENT_COLOR, l_menu, width=1, border_radius=8)

                old_clip = sub_screen.get_clip()
                sub_screen.set_clip(l_menu)
                for idx, l in enumerate(loaders_list):
                    item_y = l_menu.y + 5 + idx * 35 - loader_scroll
                    sub_screen.blit(font_main.render(l.upper(), True, text_c), (l_menu.x + 15, item_y + 8))
                sub_screen.set_clip(old_clip)

            pygame.display.flip()
            clock.tick(60)
    except Exception as e:
        print(f"Error in filter window: {e}")

# ==========================================
# VERSION CREATOR PROCESS WINDOW
# ==========================================

# ==========================================
# VERSION RIBBON UI HELPERS
# ==========================================

def _version_ribbon_metrics(ribbon_rect, versions_count, scroll_offset):
    """Возвращает все параметры ленты в одном словаре.

    Словарь намеренно используется вместо tuple-unpack, чтобы исключить
    ошибки вида "expected N, got M" при изменениях интерфейса.
    """
    row_height = 36
    row_gap = 6
    pad = 10
    scrollbar_width = 12
    scrollbar_gap = 10

    list_rect = pygame.Rect(
        ribbon_rect.x + pad,
        ribbon_rect.y + pad,
        max(120, ribbon_rect.width - pad * 2 - scrollbar_width - scrollbar_gap),
        max(60, ribbon_rect.height - pad * 2),
    )

    visible_count = max(1, (list_rect.height + row_gap) // (row_height + row_gap))
    max_scroll = max(0, versions_count - visible_count)
    scroll = max(0, min(int(scroll_offset), max_scroll))

    track_rect = pygame.Rect(
        list_rect.right + scrollbar_gap,
        ribbon_rect.y + pad,
        scrollbar_width,
        max(30, ribbon_rect.height - pad * 2),
    )

    if max_scroll <= 0:
        thumb_rect = pygame.Rect(track_rect)
    else:
        thumb_h = max(30, int(track_rect.height * visible_count / max(1, versions_count)))
        travel = max(0, track_rect.height - thumb_h)
        ratio = scroll / max_scroll if max_scroll else 0.0
        thumb_rect = pygame.Rect(
            track_rect.x,
            track_rect.y + int(travel * ratio),
            track_rect.width,
            thumb_h,
        )

    rows = []
    for pos in range(visible_count):
        idx = scroll + pos
        if idx >= versions_count:
            break
        y = list_rect.y + pos * (row_height + row_gap)
        rows.append((idx, pygame.Rect(list_rect.x, y, list_rect.width, row_height)))

    return {
        "list_rect": list_rect,
        "track_rect": track_rect,
        "thumb_rect": thumb_rect,
        "visible_count": visible_count,
        "max_scroll": max_scroll,
        "scroll": scroll,
        "rows": rows,
        "row_height": row_height,
        "row_gap": row_gap,
    }


def _version_ribbon_scroll_from_mouse(metrics, mouse_y):
    """Получает индекс прокрутки по позиции мыши на вертикальном слайдере."""
    max_scroll = metrics["max_scroll"]
    if max_scroll <= 0:
        return 0

    track_rect = metrics["track_rect"]
    thumb_rect = metrics["thumb_rect"]
    travel = max(1, track_rect.height - thumb_rect.height)
    offset = mouse_y - track_rect.y - thumb_rect.height // 2
    ratio = max(0.0, min(1.0, offset / travel))
    return int(round(ratio * max_scroll))


def _version_ribbon_index_at(metrics, mouse_pos):
    """Возвращает индекс версии под курсором или None."""
    for idx, rect in metrics["rows"]:
        if rect.collidepoint(mouse_pos):
            return idx
    return None


def _draw_version_ribbon(surface, ribbon_rect, versions, selected_idx, scroll_offset, theme, dragging=False):
    """Красивая вертикальная лента версий + ползунок справа."""
    _, card_c, text_c, gray_c = _version_editor_colors(theme)
    metrics = _version_ribbon_metrics(ribbon_rect, len(versions), scroll_offset)

    pygame.draw.rect(surface, card_c, ribbon_rect, border_radius=12)
    pygame.draw.rect(surface, BORDER_COLOR, ribbon_rect, width=1, border_radius=12)

    list_rect = metrics["list_rect"]
    track_rect = metrics["track_rect"]
    thumb_rect = metrics["thumb_rect"]

    pygame.draw.rect(surface, INPUT_BG, list_rect, border_radius=8)

    old_clip = surface.get_clip()
    surface.set_clip(list_rect)

    for idx, row_rect in metrics["rows"]:
        selected = idx == selected_idx
        fill = ACCENT_COLOR if selected else PANEL_BG
        border = ACCENT_COLOR if selected else BORDER_COLOR
        pygame.draw.rect(surface, fill, row_rect, border_radius=8)
        pygame.draw.rect(surface, border, row_rect, width=1, border_radius=8)

        text = font_main.render(str(versions[idx]), True, TEXT_COLOR if selected else text_c)
        surface.blit(text, (row_rect.x + 12, row_rect.centery - text.get_height() // 2))

        if selected:
            mark = font_main.render("✓", True, TEXT_COLOR)
            surface.blit(mark, (row_rect.right - mark.get_width() - 12, row_rect.centery - mark.get_height() // 2))

    surface.set_clip(old_clip)

    # Вертикальный слайдер справа.
    pygame.draw.rect(surface, INPUT_BG, track_rect, border_radius=6)
    pygame.draw.rect(
        surface,
        ACCENT_COLOR if dragging else ACCENT_HOVER,
        thumb_rect,
        border_radius=6,
    )

    hint = "Нажмите версию или перетащите ползунок"
    hint_surf = font_small.render(hint, True, gray_c)
    if hint_surf.get_width() <= ribbon_rect.width - 30:
        surface.blit(hint_surf, (ribbon_rect.x + 10, ribbon_rect.bottom - hint_surf.get_height() - 4))

    return metrics


# ==========================================
# VERSION CREATOR PROCESS WINDOW
# ==========================================

def run_mod_details_process(slug, target_version, loader, mods_dir, theme):
    try:
        pygame.init()
        screen = pygame.display.set_mode((760, 650), pygame.RESIZABLE)
        pygame.display.set_caption("Mace Launcher - Детали мода")
        init_fonts()
        clock = pygame.time.Clock()

        project = get_modrinth_project_info(slug) or {}
        versions = get_modrinth_project_versions(slug) or []
        selected_tab = "info"
        active_version = get_latest_compatible_mod_version(slug, target_version, loader)
        status_text = "Готово"
        scroll_offset = 0
        drag_scrollbar = False

        def wrap_text_block(text, width, font):
            if not text:
                return ["Описание отсутствует."]
            lines = []
            for paragraph in str(text).splitlines() or [str(text)]:
                if not paragraph.strip():
                    lines.append("")
                    continue
                words = paragraph.split()
                cur = ""
                for w in words:
                    test = w if not cur else cur + " " + w
                    if font.size(test)[0] <= width:
                        cur = test
                    else:
                        if cur:
                            lines.append(cur)
                        cur = w
                if cur:
                    lines.append(cur)
            return lines

        def get_panel_content_height(panel_width, panel_height):
            if selected_tab == "info":
                wrapped = wrap_text_block(project.get("body") or project.get("description") or "Нет описания.", panel_width - 32, font_main)
                return max(panel_height, len(wrapped) * 22 + 24)
            if selected_tab == "versions":
                if not versions:
                    return panel_height
                return max(panel_height, len(versions) * 22 + 20)
            if selected_tab == "dependencies":
                deps = project.get("dependencies") or []
                if not deps:
                    return panel_height
                return max(panel_height, len(deps) * 22 + 20)
            info_lines = [
                f"Автор: {project.get('author') or 'Неизвестно'}",
                f"Загрузок: {project.get('downloads', 0)}",
                f"Категории: {', '.join(project.get('categories', [])[:5]) or '—'}",
                f"Лоадеры: {', '.join(project.get('loaders', [])[:5]) or '—'}",
            ]
            return max(panel_height, len(info_lines) * 24 + 30)

        header_icon = get_mod_icon_surface(project, size=(84, 84))
        header_title = project.get("title") or slug
        desc = (project.get("description") or "Нет описания.")
        body = project.get("body") or desc
        dependencies = project.get("dependencies") or []

        while True:
            cur_w, cur_h = screen.get_size()
            header_rect = pygame.Rect(10, 10, cur_w - 20, 110)
            tabs_rects = [
                ("info", pygame.Rect(150, 135, 110, 38)),
                ("versions", pygame.Rect(270, 135, 110, 38)),
                ("dependencies", pygame.Rect(390, 135, 130, 38)),
                ("details", pygame.Rect(530, 135, 110, 38)),
            ]
            panel_rect = pygame.Rect(20, 185, cur_w - 40, cur_h - 250)
            panel_inner = pygame.Rect(panel_rect.x + 10, panel_rect.y + 10, panel_rect.width - 28, panel_rect.height - 20)
            update_btn = pygame.Rect(cur_w - 150, cur_h - 62, 130, 42)
            status_panel = pygame.Rect(20, cur_h - 72, cur_w - 200, 52)
            scrollbar_track = pygame.Rect(panel_rect.right - 12, panel_rect.y + 8, 8, panel_rect.height - 16)

            content_height = get_panel_content_height(panel_inner.width, panel_inner.height)
            max_scroll = max(0, content_height - panel_inner.height)
            scroll_offset = max(0, min(scroll_offset, max_scroll))

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = event.pos
                    for tab_name, rect in tabs_rects:
                        if rect.collidepoint(pos):
                            selected_tab = tab_name
                            break
                    if update_btn.collidepoint(pos) and active_version:
                        def do_update():
                            ok, msg = install_selected_mod_version(slug, target_version, loader, mods_dir, version_info=active_version)
                            if not ok:
                                print(f"Ошибка установки мода: {msg}")
                            else:
                                print(f"Мод {slug} успешно обновлён: {msg}")
                        threading.Thread(target=do_update, daemon=True).start()
                        status_text = "Загрузка запущена..."
                    elif scrollbar_track.collidepoint(pos):
                        drag_scrollbar = True
                        rel = pos[1] - scrollbar_track.y
                        thumb_h = max(30, int(scrollbar_track.height * (panel_inner.height / max(1, content_height))))
                        if thumb_h < scrollbar_track.height:
                            ratio = max(0.0, min(1.0, (rel - thumb_h / 2) / max(1, scrollbar_track.height - thumb_h)))
                            scroll_offset = int(ratio * max_scroll)
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    drag_scrollbar = False
                elif event.type == pygame.MOUSEMOTION and drag_scrollbar:
                    if scrollbar_track.collidepoint(event.pos):
                        thumb_h = max(30, int(scrollbar_track.height * (panel_inner.height / max(1, content_height))))
                        travel = max(1, scrollbar_track.height - thumb_h)
                        offset = max(0, min(event.pos[1] - scrollbar_track.y, travel))
                        ratio = offset / travel
                        scroll_offset = int(ratio * max_scroll)
                elif event.type == pygame.MOUSEWHEEL:
                    if panel_rect.collidepoint(pygame.mouse.get_pos()):
                        scroll_offset = max(0, min(scroll_offset - event.y * 18, max_scroll))

            screen.fill((18, 18, 24))

            pygame.draw.rect(screen, (30, 30, 38), header_rect, border_radius=16)
            pygame.draw.rect(screen, (40, 40, 52), header_rect.inflate(-10, -10), border_radius=12)
            screen.blit(header_icon, (header_rect.x + 18, header_rect.y + 12))

            title_surf = font_title.render(header_title[:30], True, (245, 245, 250))
            screen.blit(title_surf, (header_rect.x + 120, header_rect.y + 20))
            slug_surf = font_small.render(f"slug: {slug}", True, (140, 145, 160))
            screen.blit(slug_surf, (header_rect.x + 120, header_rect.y + 50))
            if active_version:
                version_name = active_version.get("name") or active_version.get("version_number") or "новая версия"
                info_surf = font_small.render(f"Последняя: {version_name}", True, (110, 210, 140))
                screen.blit(info_surf, (header_rect.x + 120, header_rect.y + 72))

            for tab_name, rect in tabs_rects:
                active = tab_name == selected_tab
                pygame.draw.rect(screen, (88, 101, 242) if active else (28, 28, 36), rect, border_radius=8)
                label = {
                    'info': 'Описание',
                    'versions': 'Версии',
                    'dependencies': 'Зависимости',
                    'details': 'Инфо',
                }[tab_name]
                txt = font_small.render(label, True, (245, 245, 250))
                screen.blit(txt, (rect.x + 16, rect.y + 11))

            pygame.draw.rect(screen, (22, 22, 28), panel_rect, border_radius=12)
            pygame.draw.rect(screen, (40, 40, 52), panel_rect, width=1, border_radius=12)

            old_clip = screen.get_clip()
            screen.set_clip(panel_inner)
            inner_y = panel_inner.y + 12 - scroll_offset

            if selected_tab == "info":
                wrapped = wrap_text_block(body, panel_inner.width - 10, font_main)
                for line in wrapped:
                    surf = font_main.render(line, True, (245, 245, 250))
                    screen.blit(surf, (panel_inner.x + 12, inner_y))
                    inner_y += 22
            elif selected_tab == "versions":
                if versions:
                    for item in versions:
                        name = item.get("name") or item.get("version_number") or "Версия"
                        summary = ", ".join(str(x) for x in item.get("game_versions", [])[:3])
                        if not summary:
                            summary = "-"
                        label = f"• {name}  ({summary})"
                        surf = font_main.render(label, True, (245, 245, 250))
                        screen.blit(surf, (panel_inner.x + 12, inner_y))
                        inner_y += 22
                else:
                    surf = font_main.render(tr("versions_not_found"), True, (140, 145, 160))
                    screen.blit(surf, (panel_inner.x + 12, inner_y))
            elif selected_tab == "dependencies":
                if dependencies:
                    for dep in dependencies:
                        dep_type = dep.get("dependency_type") or "dependency"
                        dep_name = dep.get("project_id") or dep.get("version_id") or "Unknown"
                        surf = font_main.render(f"• {dep_type}: {dep_name}", True, (245, 245, 250))
                        screen.blit(surf, (panel_inner.x + 12, inner_y))
                        inner_y += 22
                else:
                    surf = font_main.render(tr("dependencies_not_set"), True, (140, 145, 160))
                    screen.blit(surf, (panel_inner.x + 12, inner_y))
            elif selected_tab == "details":
                info_lines = [
                    f"Автор: {project.get('author') or 'Неизвестно'}",
                    f"Загрузок: {project.get('downloads', 0)}",
                    f"Категории: {', '.join(project.get('categories', [])[:5]) or '—'}",
                    f"Лоадеры: {', '.join(project.get('loaders', [])[:5]) or '—'}",
                ]
                for line in info_lines:
                    surf = font_main.render(line, True, (245, 245, 250))
                    screen.blit(surf, (panel_inner.x + 12, inner_y))
                    inner_y += 24

            screen.set_clip(old_clip)

            if content_height > panel_inner.height:
                thumb_h = max(30, int(scrollbar_track.height * (panel_inner.height / max(1, content_height))))
                travel = max(1, scrollbar_track.height - thumb_h)
                thumb_y = scrollbar_track.y + int((scroll_offset / max_scroll) * travel)
                pygame.draw.rect(screen, (36, 36, 44), scrollbar_track, border_radius=6)
                pygame.draw.rect(screen, (90, 100, 245), pygame.Rect(scrollbar_track.x, thumb_y, scrollbar_track.width, thumb_h), border_radius=6)
            else:
                pygame.draw.rect(screen, (28, 28, 36), scrollbar_track, border_radius=6)

            pygame.draw.rect(screen, (64, 169, 95), update_btn, border_radius=10)
            btn_text = font_main.render(tr("update_mod"), True, (245, 245, 250))
            screen.blit(btn_text, (update_btn.centerx - btn_text.get_width() // 2, update_btn.centery - btn_text.get_height() // 2))

            pygame.draw.rect(screen, (28, 28, 36), status_panel, border_radius=10)
            status_surf = font_main.render(status_text, True, (220, 220, 220))
            screen.blit(status_surf, (status_panel.x + 15, status_panel.y + 15))

            pygame.display.flip()
            clock.tick(60)
    except Exception as exc:
        print(f"Ошибка окна мода: {exc}")
        traceback.print_exc()


def run_detached_module_process(module_id, theme, skin_path, shared_logs, bg_cfg=None):
    """Отдельное окно для отображения содержимого конкретного модуля.

    В отличие от простого заглушечного экрана, здесь рендерятся данные,
    характерные для нужного блока интерфейса: профиль, системная информация,
    консоль логов, превью скина и содержимое мод-брозера.
    """
    try:
        pygame.init()
        screen = pygame.display.set_mode((520, 420), pygame.RESIZABLE)
        pygame.display.set_caption(f"Mace Launcher - {module_id.upper()} (Detached)")
        init_fonts()
        clock = pygame.time.Clock()

        dark = theme == "dark"
        bg = (14, 14, 18) if dark else (235, 238, 242)
        panel = (28, 28, 36) if dark else (245, 247, 250)
        panel_alt = (22, 22, 28) if dark else (240, 242, 246)
        border = (40, 40, 52) if dark else (210, 215, 225)
        text = (245, 245, 250) if dark else (20, 20, 25)
        gray = (140, 145, 160) if dark else (110, 115, 130)
        accent = ACCENT_COLOR
        success = SUCCESS_COLOR
        danger = DANGER_COLOR

        def safe_lines(data, limit=8):
            if not data:
                return [tr("no_logs_yet")]
            lines = []
            for item in list(data)[-limit:]:
                text_line = str(item)
                if len(text_line) > 90:
                    text_line = text_line[:87] + "..."
                lines.append(text_line)
            return lines or [tr("no_logs_yet")]

        console_offset = 0
        while True:
            panel_rect = pygame.Rect(20, 60, screen.get_width() - 40, screen.get_height() - 85)
            inner = panel_rect.inflate(-14, -14)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return
                if event.type == pygame.MOUSEWHEEL and module_id == "console":
                    if event.y != 0:
                        lines = normalize_console_lines(shared_logs if shared_logs is not None else get_live_logs())
                        max_visible = max(4, (panel_rect.height - 96) // 18)
                        max_scroll = max(0, len(lines) - max_visible)
                        console_offset = max(0, min(console_offset + int(-event.y * 2), max_scroll))
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and module_id == "console":
                    copy_btn = pygame.Rect(inner.right - 104, inner.y + 14, 90, 22)
                    scroll_track = pygame.Rect(inner.right - 14, inner.y + 30, 6, inner.height - 60)
                    if copy_btn.collidepoint(event.pos):
                        copy_to_clipboard("\n".join(normalize_console_lines(shared_logs if shared_logs is not None else get_live_logs())))
                        add_log("[UI] Console log copied from detached window.")
                    elif scroll_track.collidepoint(event.pos):
                        lines = normalize_console_lines(shared_logs if shared_logs is not None else get_live_logs())
                        max_visible = max(4, (panel_rect.height - 96) // 18)
                        max_scroll = max(0, len(lines) - max_visible)
                        if max_scroll > 0:
                            ratio = max(0.0, min(1.0, (event.pos[1] - scroll_track.y) / max(1, scroll_track.height)))
                            console_offset = int(ratio * max_scroll)

            screen.fill(bg)
            title = font_subtitle.render(f"{tr('module')}: {module_id}", True, text)
            screen.blit(title, (20, 20))

            panel_rect = pygame.Rect(20, 60, screen.get_width() - 40, screen.get_height() - 85)
            pygame.draw.rect(screen, panel, panel_rect, border_radius=12)
            pygame.draw.rect(screen, border, panel_rect, width=1, border_radius=12)

            inner = panel_rect.inflate(-14, -14)
            label = font_small.render(tr("state"), True, gray)
            screen.blit(label, (inner.x + 10, inner.y + 8))

            if module_id == "info":
                draw_info_module_content(screen, pygame.Rect(inner.x, inner.y + 20, inner.width, inner.height - 20), 60)
            elif module_id == "console":
                log_box = pygame.Rect(inner.x + 8, inner.y + 24, inner.width - 16, inner.height - 56)
                copy_btn = pygame.Rect(log_box.right - 102, log_box.y + 8, 90, 22)
                scroll_track = pygame.Rect(log_box.right - 14, log_box.y + 8, 6, log_box.height - 16)
                pygame.draw.rect(screen, panel_alt, log_box, border_radius=8)
                pygame.draw.rect(screen, border, log_box, width=1, border_radius=8)
                pygame.draw.rect(screen, CARD_BG, copy_btn, border_radius=6)
                pygame.draw.rect(screen, BORDER_COLOR, copy_btn, width=1, border_radius=6)
                screen.blit(font_small.render(tr("copy_log"), True, TEXT_COLOR), (copy_btn.x + 8, copy_btn.y + 5))

                live_logs = normalize_console_lines(shared_logs if shared_logs is not None else get_live_logs())
                log_lines = live_logs
                max_visible = max(4, (log_box.height - 18) // 18)
                max_scroll = max(0, len(log_lines) - max_visible)
                console_offset = max(0, min(console_offset, max_scroll))
                visible = log_lines[console_offset:console_offset + max_visible]

                offset = 0
                for line in visible:
                    clean_line = str(line)
                    if len(clean_line) > 96:
                        clean_line = clean_line[:93] + "..."
                    surf = font_console.render(clean_line, True, CONSOLE_TEXT if "Error" not in clean_line.lower() and "warning" not in clean_line.lower() and "fail" not in clean_line.lower() else (255, 180, 180))
                    screen.blit(surf, (log_box.x + 10, log_box.y + 10 + offset))
                    offset += 18
                if not visible:
                    empty = font_console.render(tr("no_logs_yet"), True, GRAY_TEXT)
                    screen.blit(empty, (log_box.x + 10, log_box.y + 10))
                if max_scroll > 0:
                    thumb_h = max(18, int((max_visible / max(1, len(log_lines))) * max(1, scroll_track.height)))
                    thumb_y = scroll_track.y + int((console_offset / max_scroll) * max(1, scroll_track.height - thumb_h))
                    pygame.draw.rect(screen, ACCENT_COLOR, pygame.Rect(scroll_track.x, thumb_y, scroll_track.width, thumb_h), border_radius=4)
                pygame.draw.rect(screen, INPUT_BG, scroll_track, border_radius=4)
                status = font_main.render(tr("console_active"), True, success)
                screen.blit(status, (log_box.x + 10, log_box.bottom - 28))
            elif module_id == "left":
                name = globals().get("username", "Your Name")
                ver = globals().get("cur_ver", "") or globals().get("selected_ver_idx", "")
                status_text = tr("game_running") if is_game_running() else tr("waiting_for_launch")
                status_color = success if is_game_running() else gray
                avatar = pygame.Surface((72, 72), pygame.SRCALPHA)
                pygame.draw.circle(avatar, accent, (36, 36), 34)
                pygame.draw.circle(avatar, (255, 255, 255, 180), (25, 25), 8)
                pygame.draw.circle(avatar, (255, 255, 255, 180), (47, 25), 8)
                pygame.draw.arc(avatar, (255, 255, 255, 180), (20, 34, 32, 22), 3.14159, 0, 3)
                screen.blit(avatar, (inner.x + 12, inner.y + 28))
                screen.blit(font_subtitle.render(name, True, text), (inner.x + 100, inner.y + 32))
                screen.blit(font_main.render(f"{tr('version')}: {ver if ver else tr('no_versions')}", True, gray), (inner.x + 100, inner.y + 64))
                screen.blit(font_main.render(f"{tr('state')}: {status_text}", True, status_color), (inner.x + 100, inner.y + 90))

                bar = pygame.Rect(inner.x + 18, inner.y + 138, inner.width - 36, 16)
                pygame.draw.rect(screen, panel_alt, bar, border_radius=8)
                pygame.draw.rect(screen, accent, pygame.Rect(bar.x, bar.y, max(10, int(bar.width * 0.72)), bar.height), border_radius=8)
                screen.blit(font_small.render(tr("memory_load"), True, gray), (inner.x + 18, inner.y + 118))
                screen.blit(font_main.render(f"RAM: {get_hardware_info()['ram_usage']}%", True, text), (inner.x + 18, inner.y + 160))
                screen.blit(font_main.render(tr("last_login_today"), True, gray), (inner.x + 18, inner.y + 188))
            elif module_id == "right":
                preview = pygame.Rect(inner.x + 16, inner.y + 28, inner.width - 32, inner.height - 96)
                pygame.draw.rect(screen, panel_alt, preview, border_radius=10)
                pygame.draw.rect(screen, border, preview, width=1, border_radius=10)
                if skin_path and os.path.exists(skin_path):
                    try:
                        skin_surface = pygame.image.load(skin_path).convert_alpha()
                        skin_surface = pygame.transform.scale(skin_surface, (max(90, preview.width - 20), max(120, preview.height - 20)))
                        screen.blit(skin_surface, (preview.centerx - skin_surface.get_width() // 2, preview.centery - skin_surface.get_height() // 2))
                    except Exception:
                        pass
                else:
                    pygame.draw.rect(screen, accent, preview.inflate(-30, -40), border_radius=12)
                    pygame.draw.circle(screen, (255, 255, 255, 160), (preview.centerx, preview.centery - 20), 18, 0)
                    pygame.draw.rect(screen, (255, 255, 255, 180), (preview.centerx - 20, preview.centery + 12, 40, 38), border_radius=8)
                label_surf = font_main.render(tr("character_skin"), True, text)
                screen.blit(label_surf, (inner.x + 16, inner.y + inner.height - 42))
            elif module_id == "center":
                browser_box = pygame.Rect(inner.x + 10, inner.y + 32, inner.width - 20, inner.height - 66)
                pygame.draw.rect(screen, panel_alt, browser_box, border_radius=10)
                pygame.draw.rect(screen, border, browser_box, width=1, border_radius=10)
                screen.blit(font_main.render(tr("mods_news_browser"), True, text), (browser_box.x + 12, browser_box.y + 12))
                screen.blit(font_small.render(tr("current_tab") + str(globals().get("center_active_tab", "news")), True, gray), (browser_box.x + 12, browser_box.y + 36))
                rows = []
                result_items = list(globals().get("cached_mod_results", []))[:3]
                if result_items:
                    rows = [item.get("title", "Mod") for item in result_items[:3]]
                else:
                    rows = ["Fabric", "Shaders", "Worldgen"]
                y = browser_box.y + 70
                for row in rows:
                    row_rect = pygame.Rect(browser_box.x + 12, y, browser_box.width - 24, 34)
                    pygame.draw.rect(screen, panel, row_rect, border_radius=6)
                    screen.blit(font_main.render(row, True, text), (row_rect.x + 12, row_rect.y + 8))
                    y += 42
                screen.blit(font_small.render(tr("scroll_loading"), True, gray), (browser_box.x + 12, browser_box.bottom - 24))
            else:
                info_text = [
                    f"{tr('module')}: {module_id}",
                    tr("widget_in_detached_window"),
                    tr("widget_syncs_with_main_interface"),
                    tr("press_esc_or_close"),
                ]
                y = inner.y + 26
                for line in info_text:
                    surf = font_main.render(line, True, text if y < inner.y + 80 else gray)
                    screen.blit(surf, (inner.x + 16, y))
                    y += 24

            pygame.display.flip()
            clock.tick(30)
    except Exception as exc:
        print(f"Ошибка detached модуля '{module_id}': {exc}")
        traceback.print_exc()


def run_version_creator_process(theme, shared_logs):
    try:
        pygame.init()
        sub_screen = pygame.display.set_mode((620, 760), pygame.RESIZABLE)
        pygame.display.set_caption("Mace Launcher - Створення нової версії")
        init_fonts()

        ver_name_input = ""
        loaders = ["fabric", "forge", "neoforge", "curseforge"]
        selected_loader_idx = 0

        available_versions = get_available_minecraft_versions()
        if not available_versions:
            available_versions = ["1.20.1"]
        available_versions = list(available_versions)

        mc_version_idx = available_versions.index("1.20.1") if "1.20.1" in available_versions else 0
        version_scroll_offset = mc_version_idx
        version_slider_dragging = False

        active_field = "name"
        status_message = tr("enter_pack_name_and_options")
        status_color = (140, 145, 160)
        clock = pygame.time.Clock()

        while True:
            cur_w, cur_h = sub_screen.get_size()
            margin = 30
            content_w = max(360, cur_w - margin * 2)

            name_rect = pygame.Rect(margin, 82, content_w, 42)
            ribbon_rect = pygame.Rect(margin, 170, content_w, 250)
            loader_label_y = 435
            loader_top = 458
            loader_gap = 10
            loader_w = (content_w - loader_gap) // 2
            loader_h = 40
            warn_rect = pygame.Rect(margin, 555, content_w, 72)
            status_rect = pygame.Rect(margin, 640, content_w, 28)
            create_btn = pygame.Rect(margin, 685, content_w, 48)

            # При уменьшении окна сохраняем интервалы, не допуская налезания.
            if cur_h < 750:
                create_btn.y = max(650, cur_h - 55)
                status_rect.y = create_btn.y - 34
                warn_rect.y = status_rect.y - warn_rect.height - 10
                loader_top = warn_rect.y - 95
                loader_label_y = loader_top - 23
                ribbon_rect.height = max(170, loader_top - ribbon_rect.bottom if False else loader_top - 180)

            metrics = _version_ribbon_metrics(ribbon_rect, len(available_versions), version_scroll_offset)
            version_scroll_offset = metrics["scroll"]
            max_scroll = metrics["max_scroll"]

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return

                if event.type == pygame.VIDEORESIZE:
                    sub_screen = pygame.display.set_mode((max(560, event.w), max(700, event.h)), pygame.RESIZABLE)
                    continue

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = event.pos

                    if name_rect.collidepoint(pos):
                        active_field = "name"
                        continue

                    if ribbon_rect.collidepoint(pos):
                        active_field = None
                        clicked = _version_ribbon_index_at(metrics, pos)
                        if clicked is not None:
                            mc_version_idx = clicked
                        elif metrics["track_rect"].collidepoint(pos):
                            version_slider_dragging = True
                            version_scroll_offset = _version_ribbon_scroll_from_mouse(metrics, pos[1])
                        continue

                    clicked_loader = False
                    for idx, l_name in enumerate(loaders):
                        col = idx % 2
                        row = idx // 2
                        l_rect = pygame.Rect(
                            margin + col * (loader_w + loader_gap),
                            loader_top + row * (loader_h + loader_gap),
                            loader_w,
                            loader_h,
                        )
                        if l_rect.collidepoint(pos):
                            selected_loader_idx = idx
                            active_field = None
                            clicked_loader = True
                            break

                    if clicked_loader:
                        continue

                    if create_btn.collidepoint(pos):
                        if not ver_name_input.strip():
                            status_message = tr("version_name_empty")
                            status_color = DANGER_COLOR
                            continue

                        version_folder = os.path.join(MINECRAFT_DIR, "versions", ver_name_input.strip())
                        if os.path.exists(version_folder):
                            status_message = tr("version_exists_message").format(name=ver_name_input)
                            status_color = DANGER_COLOR
                            continue

                        selected_mc_version = available_versions[mc_version_idx]
                        status_message = tr("creating_pack_files")
                        status_color = (255, 193, 7)
                        pygame.display.flip()

                        success, msg = create_new_version(
                            ver_name_input.strip(),
                            selected_mc_version,
                            loaders[selected_loader_idx],
                        )
                        status_message = msg
                        status_color = SUCCESS_COLOR if success else DANGER_COLOR
                    continue

                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    version_slider_dragging = False

                elif event.type == pygame.MOUSEMOTION and version_slider_dragging:
                    version_scroll_offset = _version_ribbon_scroll_from_mouse(metrics, event.pos[1])
                    if max_scroll > 0:
                        version_scroll_offset = max(0, min(max_scroll, version_scroll_offset))

                elif event.type == pygame.MOUSEWHEEL:
                    if ribbon_rect.collidepoint(pygame.mouse.get_pos()):
                        version_scroll_offset = max(0, min(max_scroll, version_scroll_offset - event.y))

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_BACKSPACE:
                        if active_field == "name":
                            ver_name_input = ver_name_input[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        active_field = None
                    elif event.unicode.isprintable() and active_field == "name" and len(ver_name_input) < 25:
                        ver_name_input += event.unicode

            bg_c = (14, 14, 18) if theme == "dark" else (235, 238, 242)
            card_c = (28, 28, 36) if theme == "dark" else (245, 247, 250)
            text_c = (245, 245, 250) if theme == "dark" else (20, 20, 25)
            sub_screen.fill(bg_c)

            title = font_subtitle.render(tr("create_version_title"), True, text_c)
            sub_screen.blit(title, (margin, 22))

            sub_screen.blit(font_small.render(tr("version_name_label"), True, GRAY_TEXT), (margin, 58))
            pygame.draw.rect(sub_screen, card_c, name_rect, border_radius=8)
            pygame.draw.rect(
                sub_screen,
                ACCENT_COLOR if active_field == "name" else BORDER_COLOR,
                name_rect,
                width=2 if active_field == "name" else 1,
                border_radius=8,
            )
            name_surf = font_main.render(ver_name_input + ("|" if active_field == "name" else ""), True, text_c)
            sub_screen.blit(name_surf, (name_rect.x + 12, name_rect.centery - name_surf.get_height() // 2))

            sub_screen.blit(font_small.render(tr("minecraft_version_label"), True, GRAY_TEXT), (margin, 146))
            metrics = _draw_version_ribbon(
                sub_screen,
                ribbon_rect,
                available_versions,
                mc_version_idx,
                version_scroll_offset,
                theme,
                version_slider_dragging,
            )
            version_scroll_offset = metrics["scroll"]

            selected_caption = font_small.render(
                f"{tr('selected')}: Minecraft {available_versions[mc_version_idx]}",
                True,
                SUCCESS_COLOR,
            )
            sub_screen.blit(selected_caption, (margin, ribbon_rect.bottom + 8))

            sub_screen.blit(font_small.render(tr("loader_label"), True, GRAY_TEXT), (margin, loader_label_y))
            for idx, l_name in enumerate(loaders):
                col = idx % 2
                row = idx // 2
                l_rect = pygame.Rect(
                    margin + col * (loader_w + loader_gap),
                    loader_top + row * (loader_h + loader_gap),
                    loader_w,
                    loader_h,
                )
                is_sel = idx == selected_loader_idx
                pygame.draw.rect(sub_screen, ACCENT_COLOR if is_sel else card_c, l_rect, border_radius=8)
                pygame.draw.rect(sub_screen, BORDER_COLOR, l_rect, width=1, border_radius=8)
                l_surf = font_main.render(l_name.upper(), True, text_c)
                sub_screen.blit(l_surf, (l_rect.centerx - l_surf.get_width() // 2, l_rect.centery - l_surf.get_height() // 2))

            pygame.draw.rect(sub_screen, PANEL_BG, warn_rect, border_radius=8)
            pygame.draw.rect(sub_screen, DANGER_COLOR, warn_rect, width=1, border_radius=8)
            sub_screen.blit(font_small.render(tr("warning_create_files"), True, DANGER_COLOR), (warn_rect.x + 12, warn_rect.y + 9))
            sub_screen.blit(font_small.render(tr("protection_name_exists"), True, GRAY_TEXT), (warn_rect.x + 12, warn_rect.y + 31))
            sub_screen.blit(font_small.render(tr("protection_blocked"), True, GRAY_TEXT), (warn_rect.x + 12, warn_rect.y + 49))

            status_surf = font_small.render(status_message, True, status_color)
            sub_screen.blit(status_surf, (status_rect.x, status_rect.y))

            pygame.draw.rect(sub_screen, SUCCESS_COLOR, create_btn, border_radius=8)
            btn_txt = font_title.render(tr("create_version_button"), True, text_c)
            sub_screen.blit(btn_txt, (create_btn.centerx - btn_txt.get_width() // 2, create_btn.centery - btn_txt.get_height() // 2))

            pygame.display.flip()
            clock.tick(60)

    except Exception as e:
        print(f"Помилка у вікні створення версії: {e}")
        traceback.print_exc()
        try:
            pygame.quit()
        except Exception:
            pass


# ==========================================
# VERSION EDITOR / CONFIRMATION WINDOWS
# ==========================================
VERSION_ACTION_LABELS = {
    "update_version": "Обновить версию",
    "update_client": "Обновить клиент",
    "update_jar": "Обновить JAR",
    "backup": "Сделать бэкап",
    "restore": "Восстановить версию",
    "delete": "Удалить мод-пак",
}


def _version_editor_colors(theme):
    if theme == "dark":
        return (14, 14, 18), (28, 28, 36), (245, 245, 250), (140, 145, 160)
    return (235, 238, 242), (245, 247, 250), (20, 20, 25), (110, 115, 130)


def run_confirmation_process(theme, action_title, version_name, details, shared_result):
    """Отдельное маленькое Pygame-окно с обязательным подтверждением опасного действия."""
    try:
        pygame.init()
        sub_screen = pygame.display.set_mode((540, 270))
        pygame.display.set_caption("Mace Launcher - Подтверждение действия")
        init_fonts()
        clock = pygame.time.Clock()
        bg_c, card_c, text_c, gray_c = _version_editor_colors(theme)

        confirmed = False
        finished = False
        yes_rect = pygame.Rect(45, 190, 210, 48)
        no_rect = pygame.Rect(285, 190, 210, 48)

        while not finished:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    finished = True
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if yes_rect.collidepoint(event.pos):
                        confirmed = True
                        finished = True
                    elif no_rect.collidepoint(event.pos):
                        finished = True

            sub_screen.fill(bg_c)
            panel = pygame.Rect(18, 18, 504, 234)
            pygame.draw.rect(sub_screen, card_c, panel, border_radius=12)
            pygame.draw.rect(sub_screen, DANGER_COLOR, panel, width=1, border_radius=12)
            title = font_subtitle.render(action_title, True, DANGER_COLOR)
            sub_screen.blit(title, (panel.centerx - title.get_width() // 2, 34))
            question = font_title.render(tr("confirm_action_question"), True, text_c)
            sub_screen.blit(question, (panel.centerx - question.get_width() // 2, 72))
            version_s = font_main.render(f"{tr('version')}: {version_name}", True, text_c)
            sub_screen.blit(version_s, (panel.centerx - version_s.get_width() // 2, 112))
            detail_s = font_small.render(details[:72], True, gray_c)
            sub_screen.blit(detail_s, (panel.centerx - detail_s.get_width() // 2, 140))
            pygame.draw.rect(sub_screen, DANGER_COLOR, yes_rect, border_radius=8)
            pygame.draw.rect(sub_screen, BORDER_COLOR, no_rect, width=1, border_radius=8)
            yes_s = font_main.render(tr("yes_continue"), True, TEXT_COLOR)
            no_s = font_main.render(tr("no"), True, text_c)
            sub_screen.blit(yes_s, (yes_rect.centerx - yes_s.get_width() // 2, yes_rect.centery - yes_s.get_height() // 2))
            sub_screen.blit(no_s, (no_rect.centerx - no_s.get_width() // 2, no_rect.centery - no_s.get_height() // 2))
            pygame.display.flip()
            clock.tick(60)

        shared_result["confirmed"] = confirmed
    except Exception as e:
        try:
            shared_result["confirmed"] = False
            shared_result["error"] = str(e)
        except Exception:
            pass
        traceback.print_exc()
    finally:
        pygame.quit()


def ask_version_confirmation(theme, action_key, version_name, details, shared_logs=None):
    """Запускает отдельное окно подтверждения и возвращает True/False."""
    manager = None
    try:
        manager = multiprocessing.Manager()
        result = manager.dict()
        result["confirmed"] = False
        p = multiprocessing.Process(
            target=run_confirmation_process,
            args=(theme, VERSION_ACTION_LABELS.get(action_key, action_key), version_name, details, result),
        )
        p.start()
        p.join()
        return bool(result.get("confirmed", False))
    finally:
        if manager is not None:
            try:
                manager.shutdown()
            except Exception:
                pass


def run_version_editor_process(theme, version_name, shared_logs):
    """Отдельное окно Pygame для управления выбранным модпаком."""
    try:
        pygame.init()
        sub_screen = pygame.display.set_mode((760, 830), pygame.RESIZABLE)
        pygame.display.set_caption(f"Mace Launcher - Редактирование версии [{version_name}]")
        init_fonts()
        clock = pygame.time.Clock()

        available_versions = get_available_minecraft_versions()
        if not available_versions:
            available_versions = [version_name]
        available_versions = list(available_versions)

        current_base = version_name
        try:
            version_json = os.path.join(MINECRAFT_DIR, "versions", version_name, f"{version_name}.json")
            with open(version_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            current_base = data.get("inheritsFrom") or data.get("assets") or data.get("id") or version_name
        except Exception:
            pass

        target_idx = available_versions.index(current_base) if current_base in available_versions else 0
        version_scroll_offset = target_idx
        version_slider_dragging = False

        status_message = tr("choose_action")
        status_color = GRAY_TEXT
        backup_list = list_version_backups()
        running = True

        def set_status(message, success=False, danger=False):
            nonlocal status_message, status_color
            status_message = message
            status_color = DANGER_COLOR if danger else (SUCCESS_COLOR if success else ACCENT_COLOR)
            try:
                if shared_logs is not None:
                    shared_logs.append(f"[Version] {message}")
            except Exception:
                pass

        def perform_action(action_key):
            nonlocal backup_list, target_idx, current_base

            if action_key == "update_version":
                target_version = available_versions[target_idx]
                if target_version == current_base:
                    set_status("Целевая версия совпадает с текущей.", danger=True)
                    return
                if not ask_version_confirmation(theme, action_key, version_name, f"Обновить Minecraft до {target_version}"):
                    set_status("Действие отменено.")
                    return
                ok, msg = update_version(version_name, target_version)

            elif action_key == "update_client":
                if not ask_version_confirmation(theme, action_key, version_name, "Старый клиент будет полностью удалён и установлен заново"):
                    set_status("Действие отменено.")
                    return
                ok, msg = update_client(version_name)

            elif action_key == "update_jar":
                if not ask_version_confirmation(theme, action_key, version_name, "Будет заменён только файл .jar"):
                    set_status("Действие отменено.")
                    return
                ok, msg = update_jar(version_name)

            elif action_key == "backup":
                if not ask_version_confirmation(theme, action_key, version_name, "Будет создана полная копия папки версии"):
                    set_status("Действие отменено.")
                    return
                ok, msg = backup_version(version_name)
                backup_list = list_version_backups()

            elif action_key == "restore":
                if version_name not in list_version_backups():
                    set_status("Бэкап этой версии не найден в vBackups.", danger=True)
                    return
                if not ask_version_confirmation(theme, action_key, version_name, "Файлы текущей версии будут заменены бэкапом"):
                    set_status("Действие отменено.")
                    return
                ok, msg = restore_version_backup(version_name)

            elif action_key == "delete":
                if not ask_version_confirmation(theme, action_key, version_name, "Папка мод-пака будет удалена без возможности отмены"):
                    set_status("Действие отменено.")
                    return
                ok, msg = delete_modpack(version_name)
                if ok:
                    set_status(msg, success=True)
                    time.sleep(0.8)
                    return "deleted"
            else:
                return

            set_status(msg, success=ok, danger=not ok)

            if action_key in ("update_version", "update_client", "update_jar") and ok:
                try:
                    version_json = os.path.join(MINECRAFT_DIR, "versions", version_name, f"{version_name}.json")
                    with open(version_json, "r", encoding="utf-8") as f:
                        fresh_data = json.load(f)
                    fresh_base = fresh_data.get("inheritsFrom") or fresh_data.get("id")
                    if fresh_base in available_versions:
                        target_idx = available_versions.index(fresh_base)
                        current_base = fresh_base
                except Exception:
                    pass

        while running:
            cur_w, cur_h = sub_screen.get_size()
            margin = 28
            gap = 10
            content_w = max(520, cur_w - margin * 2)

            header_h = 72
            ribbon_rect = pygame.Rect(margin, 92, content_w, 220)

            update_card = pygame.Rect(margin, 324, content_w, 92)
            update_btn = pygame.Rect(update_card.x + 12, update_card.y + 38, 150, 42)
            update_label_x = update_btn.right + 14

            client_card = pygame.Rect(margin, update_card.bottom + gap, content_w, 82)
            half_w = (client_card.width - 36) // 2
            client_btn = pygame.Rect(client_card.x + 12, client_card.y + 36, half_w, 34)
            jar_btn = pygame.Rect(client_btn.right + 12, client_card.y + 36, half_w, 34)

            backup_card = pygame.Rect(margin, client_card.bottom + gap, content_w, 98)
            backup_btn = pygame.Rect(backup_card.x + 12, backup_card.y + 36, half_w, 38)
            restore_btn = pygame.Rect(backup_btn.right + 12, backup_card.y + 36, half_w, 38)

            delete_btn = pygame.Rect(margin, backup_card.bottom + gap, content_w, 44)
            status_box = pygame.Rect(margin, delete_btn.bottom + gap, content_w, 44)
            close_btn = pygame.Rect(max(margin, cur_w - 168), cur_h - 50, 140, 38)

            metrics = _version_ribbon_metrics(ribbon_rect, len(available_versions), version_scroll_offset)
            version_scroll_offset = metrics["scroll"]

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.VIDEORESIZE:
                    sub_screen = pygame.display.set_mode((max(680, event.w), max(650, event.h)), pygame.RESIZABLE)

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = event.pos

                    if close_btn.collidepoint(pos):
                        running = False

                    elif update_btn.collidepoint(pos):
                        result = perform_action("update_version")
                        if result == "deleted":
                            running = False

                    elif client_btn.collidepoint(pos):
                        result = perform_action("update_client")
                        if result == "deleted":
                            running = False

                    elif jar_btn.collidepoint(pos):
                        result = perform_action("update_jar")
                        if result == "deleted":
                            running = False

                    elif backup_btn.collidepoint(pos):
                        perform_action("backup")

                    elif restore_btn.collidepoint(pos):
                        result = perform_action("restore")
                        if result == "deleted":
                            running = False

                    elif delete_btn.collidepoint(pos):
                        result = perform_action("delete")
                        if result == "deleted":
                            running = False

                    elif ribbon_rect.collidepoint(pos):
                        clicked = _version_ribbon_index_at(metrics, pos)
                        if clicked is not None:
                            target_idx = clicked
                        elif metrics["track_rect"].collidepoint(pos):
                            version_slider_dragging = True
                            version_scroll_offset = _version_ribbon_scroll_from_mouse(metrics, pos[1])

                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    version_slider_dragging = False

                elif event.type == pygame.MOUSEMOTION and version_slider_dragging:
                    version_scroll_offset = _version_ribbon_scroll_from_mouse(metrics, event.pos[1])

                elif event.type == pygame.MOUSEWHEEL:
                    if ribbon_rect.collidepoint(pygame.mouse.get_pos()):
                        version_scroll_offset = max(0, min(metrics["max_scroll"], version_scroll_offset - event.y))

            bg_c, card_c, text_c, gray_c = _version_editor_colors(theme)
            sub_screen.fill(bg_c)

            title = font_title.render(tr("edit_version_title"), True, text_c)
            sub_screen.blit(title, (margin, 22))
            ver_title = font_subtitle.render(version_name, True, ACCENT_COLOR)
            sub_screen.blit(ver_title, (margin, 52))

            sub_screen.blit(font_small.render(tr("target_minecraft_version"), True, gray_c), (margin, 78))
            metrics = _draw_version_ribbon(
                sub_screen,
                ribbon_rect,
                available_versions,
                target_idx,
                version_scroll_offset,
                theme,
                version_slider_dragging,
            )
            version_scroll_offset = metrics["scroll"]

            pygame.draw.rect(sub_screen, card_c, update_card, border_radius=12)
            pygame.draw.rect(sub_screen, BORDER_COLOR, update_card, width=1, border_radius=12)
            sub_screen.blit(font_small.render(tr("update_version_title"), True, gray_c), (update_card.x + 12, update_card.y + 10))
            pygame.draw.rect(sub_screen, SUCCESS_COLOR, update_btn, border_radius=8)
            update_text = font_main.render(tr("update"), True, TEXT_COLOR)
            sub_screen.blit(update_text, (update_btn.centerx - update_text.get_width() // 2, update_btn.centery - update_text.get_height() // 2))

            selected_label = font_main.render(f"{tr('to')} Minecraft {available_versions[target_idx]}", True, text_c)
            sub_screen.blit(selected_label, (update_label_x, update_btn.centery - selected_label.get_height() // 2))

            pygame.draw.rect(sub_screen, card_c, client_card, border_radius=12)
            pygame.draw.rect(sub_screen, BORDER_COLOR, client_card, width=1, border_radius=12)
            sub_screen.blit(font_small.render(tr("update_client_title"), True, gray_c), (client_card.x + 12, client_card.y + 10))
            pygame.draw.rect(sub_screen, ACCENT_COLOR, client_btn, border_radius=8)
            pygame.draw.rect(sub_screen, ACCENT_COLOR, jar_btn, border_radius=8)
            client_s = font_main.render(tr("update_client"), True, TEXT_COLOR)
            jar_s = font_main.render(tr("update_jar"), True, TEXT_COLOR)
            sub_screen.blit(client_s, (client_btn.centerx - client_s.get_width() // 2, client_btn.centery - client_s.get_height() // 2))
            sub_screen.blit(jar_s, (jar_btn.centerx - jar_s.get_width() // 2, jar_btn.centery - jar_s.get_height() // 2))

            pygame.draw.rect(sub_screen, card_c, backup_card, border_radius=12)
            pygame.draw.rect(sub_screen, BORDER_COLOR, backup_card, width=1, border_radius=12)
            sub_screen.blit(font_small.render(tr("backup_title"), True, gray_c), (backup_card.x + 12, backup_card.y + 10))
            pygame.draw.rect(sub_screen, SUCCESS_COLOR, backup_btn, border_radius=8)
            pygame.draw.rect(sub_screen, card_c, restore_btn, border_radius=8)
            pygame.draw.rect(sub_screen, BORDER_COLOR, restore_btn, width=1, border_radius=8)
            backup_s = font_main.render(tr("backup"), True, TEXT_COLOR)
            restore_s = font_main.render(tr("restore"), True, text_c)
            sub_screen.blit(backup_s, (backup_btn.centerx - backup_s.get_width() // 2, backup_btn.centery - backup_s.get_height() // 2))
            sub_screen.blit(restore_s, (restore_btn.centerx - restore_s.get_width() // 2, restore_btn.centery - restore_s.get_height() // 2))

            pygame.draw.rect(sub_screen, DANGER_COLOR, delete_btn, border_radius=8)
            delete_s = font_main.render(tr("delete_modpack"), True, TEXT_COLOR)
            sub_screen.blit(delete_s, (delete_btn.centerx - delete_s.get_width() // 2, delete_btn.centery - delete_s.get_height() // 2))

            pygame.draw.rect(sub_screen, card_c, status_box, border_radius=8)
            pygame.draw.rect(sub_screen, BORDER_COLOR, status_box, width=1, border_radius=8)
            status_s = font_small.render(status_message, True, status_color)
            sub_screen.blit(status_s, (status_box.x + 12, status_box.centery - status_s.get_height() // 2))

            pygame.draw.rect(sub_screen, card_c, close_btn, border_radius=8)
            pygame.draw.rect(sub_screen, BORDER_COLOR, close_btn, width=1, border_radius=8)
            close_s = font_main.render(tr("close"), True, text_c)
            sub_screen.blit(close_s, (close_btn.centerx - close_s.get_width() // 2, close_btn.centery - close_s.get_height() // 2))

            pygame.display.flip()
            clock.tick(60)

    except Exception as e:
        print(f"Ошибка редактора версии: {e}")
        traceback.print_exc()
    finally:
        pygame.quit()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    ensure_backgrounds_dir()

    manager = multiprocessing.Manager()
    shared_logs_manager = manager.list(logs)
    shared_filter_dict = manager.dict({
        "version": "1.20.1",
        "loader": "fabric",
        "sort_asc": True
    })

    pygame.init()
    clock = pygame.time.Clock()

    MIN_WIDTH, MIN_HEIGHT = 1180, 720
    WIDTH, HEIGHT = 1250, 760

    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("Mace Launcher")

    build_picker_surface()
    init_fonts()

    config = load_config()
    ui_language = str(config.get("language", ui_language or "en")).strip() or "en"
    translator.set_language(ui_language)
    username = config.get("username", "Enter name")
    saved_version = config.get("last_version", "")
    nickname_profiles = config.get("nickname_profiles", {})
    if not isinstance(nickname_profiles, dict):
        nickname_profiles = {}
    nickname_profiles = {str(k): str(v) for k, v in nickname_profiles.items() if str(k).strip()}
    active_nickname = str(config.get("active_nickname", username) or username)
    if active_nickname not in nickname_profiles and username:
        nickname_profiles[username] = saved_version or ""
    if active_nickname not in nickname_profiles and nickname_profiles:
        active_nickname = next(iter(nickname_profiles))
    if active_nickname in nickname_profiles:
        username = active_nickname
        if nickname_profiles[active_nickname] in get_installed_versions():
            saved_version = nickname_profiles[active_nickname]
    current_theme = config.get("theme", "dark")
    accent_idx = config.get("accent_idx", 0)
    custom_color = tuple(config.get("custom_color", [255, 0, 128]))
    ram_gb = config.get("ram_gb", 4)
    ram_protection = config.get("ram_protection", True)
    launch_action = config.get("launch_action", "close")
    auto_backup_enabled = config.get("auto_backup_enabled", False)
    always_on_top = bool(config.get("always_on_top", False))
    auto_disable_incompatible_mods = bool(config.get("auto_disable_incompatible_mods", False))
    check_updates_on_start = bool(config.get("check_updates_on_start", True))
    sound_notifications = bool(config.get("sound_notifications", True))
    open_error_log_on_failed_launch = bool(config.get("open_error_log_on_failed_launch", False))
    auto_start = bool(config.get("auto_start", False))
    interface_scale = float(config.get("interface_scale", 1.0) or 1.0)
    skin_path = config.get("skin_path", "")
    favorite_versions = [str(v) for v in config.get("favorite_versions", []) if str(v).strip()]

    bg_mode = config.get("bg_mode", "preset")
    bg_preset = config.get("bg_preset", "None")
    bg_custom_path = config.get("bg_custom_path", "")
    bg_pattern_color = tuple(config.get("bg_pattern_color", list(ACCENT_COLOR)))

    grid_weights_w = config.get("grid_weights_w", [1.0, 1.5, 1.0])
    grid_weights_h = config.get("grid_weights_h", [1.0, 1.2])

    detached_modules = config.get("detached_modules", [])
    active_processes = {}

    module_layouts = config.get("module_layouts", DEFAULT_LAYOUTS)

    if "info" not in module_layouts:
        module_layouts["info"] = {"col": 2, "row": 1, "span_w": 1, "span_h": 1}
    if "console" not in module_layouts:
        module_layouts["console"] = {"col": 0, "row": 1, "span_w": 1, "span_h": 1}
    if "center" not in module_layouts:
        module_layouts["center"] = {"col": 1, "row": 0, "span_w": 1, "span_h": 2}

    edit_layout_mode = False
    dragged_module = None
    resizing_module = None
    resizing_grid_col = None
    resizing_grid_row = None
    drag_offset_x = 0
    drag_offset_y = 0

    load_skin_file(skin_path)

    temp_theme = current_theme
    temp_accent_idx = accent_idx
    temp_custom_color = custom_color
    temp_ram_gb = ram_gb
    temp_ram_protection = ram_protection
    temp_launch_action = launch_action
    temp_auto_backup_enabled = auto_backup_enabled
    temp_always_on_top = always_on_top
    temp_auto_disable_incompatible_mods = auto_disable_incompatible_mods
    temp_check_updates_on_start = check_updates_on_start
    temp_sound_notifications = sound_notifications
    temp_open_error_log_on_failed_launch = open_error_log_on_failed_launch
    temp_auto_start = auto_start
    temp_interface_scale = interface_scale
    temp_ui_language = ui_language

    temp_bg_mode = bg_mode
    temp_bg_preset = bg_preset
    temp_bg_custom_path = bg_custom_path
    temp_bg_pattern_color = bg_pattern_color

    update_theme_colors()
    set_window_topmost(always_on_top)
    if check_updates_on_start:
        has_update, version = check_for_launcher_updates_now()
        if has_update:
            add_log(f"[Update] Update available: {version or 'archive'}")

    current_page = "main"      
    settings_tab = "general"       
    center_active_tab = "news"     # internal id kept for backward compatibility; visible title is Главная

    input_active = False
    modrinth_input_active = False
    modrinth_input_text = ""
    mod_browser_search_text = ""
    mod_browser_search_active = False
    downloaded_mod_search_text = ""
    downloaded_mod_search_active = False
    downloaded_mod_scroll_offset = 0
    cached_mod_results = []
    last_browser_search_query = None

    rp_browser_search_text = ""
    rp_browser_search_active = False
    cached_rp_results = []
    last_rp_browser_search_query = None
    rp_browser_api_offset = 0
    rp_browser_total_hits = 0
    rp_browser_is_loading_more = False
    rp_browser_scroll_offset = 0
    pending_rp_search_results.clear()
    
    versions = sort_versions_with_favorites(get_installed_versions())

    selected_ver_idx = get_newest_version_index(versions)
    if saved_version in versions:
        selected_ver_idx = versions.index(saved_version)

    if versions and selected_ver_idx != -1:
        shared_filter_dict["version"] = versions[selected_ver_idx]
    cur_ver = versions[selected_ver_idx] if selected_ver_idx != -1 and len(versions) > 0 else ""
    if active_nickname:
        nickname_profiles[active_nickname] = cur_ver
    mods_dir_path = get_target_mods_dir(cur_ver)

    dropdown_open = False
    was_game_running = False
    color_picker_open = False
    bg_color_picker_open = False
    is_dragging_scrollbar = False
    is_dragging_mods_scrollbar = False
    is_dragging_browser_scrollbar = False
    local_mods = []
    content_refresh_at = 0.0
    CONTENT_REFRESH_SECONDS = 0.5
    close_after_launch = False

    bg_cfg_dict = {
        "mode": bg_mode,
        "preset": bg_preset,
        "custom_path": bg_custom_path,
        "color": bg_pattern_color
    }

    for m_id in list(detached_modules):
        try:
            p = multiprocessing.Process(
                target=run_detached_module_process,
                args=(m_id, current_theme, skin_path, shared_logs_manager, bg_cfg_dict)
            )
            p.start()
            active_processes[m_id] = p
        except Exception as e:
            print(f"Не удалось восстановить процесс {m_id}: {e}")

    while True:
        cur_w, cur_h = screen.get_size()
        mouse_pos = pygame.mouse.get_pos()
        running_state = is_game_running()
        ticks = pygame.time.get_ticks()

        if close_after_launch and not is_ui_activity_active("launch"):
            close_after_launch = False
            if running_state:
                pygame.quit()
                while is_game_running():
                    pygame.time.wait(500)
                reopen_pygame_window(cur_w, cur_h)
                add_log("[System] Игра завершена. Лаунчер перезапущен.")
                continue

        # Only the main thread mutates the visible browser state. Worker threads
        # place completed network requests in this queue, keeping the interface
        # responsive enough for the spinner to animate.
        with ui_activity_lock:
            browser_results = pending_browser_search_results[:]
            pending_browser_search_results.clear()
        for result in browser_results:
            if result["query_key"] != last_browser_search_query:
                continue
            if result["reset"]:
                cached_mod_results = result["hits"]
                mod_browser_api_offset = len(cached_mod_results)
            elif result["offset"] == mod_browser_api_offset:
                cached_mod_results.extend(result["hits"])
                mod_browser_api_offset += len(result["hits"])
            mod_browser_total_hits = result["total"]
            mod_browser_is_loading_more = False
            if len(cached_mod_results) > mod_browser_max_cached:
                drop_count = len(cached_mod_results) - mod_browser_max_cached
                cached_mod_results = cached_mod_results[drop_count:]
                mod_browser_scroll_offset = max(0, mod_browser_scroll_offset - drop_count * 65)

        with ui_activity_lock:
            rp_results = pending_rp_search_results[:]
            pending_rp_search_results.clear()
        for result in rp_results:
            if result.get("query_key") != last_rp_browser_search_query:
                continue
            hits = result.get("hits", []) or []
            if result.get("reset"):
                cached_rp_results = hits
                rp_browser_api_offset = len(hits)
            elif result.get("offset") == rp_browser_api_offset:
                cached_rp_results.extend(hits)
                rp_browser_api_offset += len(hits)
            rp_browser_is_loading_more = False
            if len(cached_rp_results) > rp_browser_max_cached:
                drop_count = len(cached_rp_results) - rp_browser_max_cached
                cached_rp_results = cached_rp_results[drop_count:]
                rp_browser_scroll_offset = max(0, rp_browser_scroll_offset - drop_count * 65)

        dt = clock.get_time()
        if dt > 0:
            frametime_history.append(dt)
            if len(frametime_history) > 40:
                frametime_history.pop(0)

        cur_fps = clock.get_fps()
        if cur_fps > 0:
            fps_history.append(cur_fps)
            if len(fps_history) > 100:
                fps_history.pop(0)

        for m_id in list(active_processes.keys()):
            if not active_processes[m_id].is_alive():
                active_processes[m_id].join()
                del active_processes[m_id]
                if m_id in detached_modules:
                    detached_modules.remove(m_id)
                add_log(f"[UI] Отдельное окно модуля '{m_id}' закрыто, возвращен на сетку.")

        if launch_action == "hide":
            if running_state and not was_game_running:
                was_game_running = True
                pygame.display.iconify()
            elif not running_state and was_game_running:
                was_game_running = False
                screen = pygame.display.set_mode((cur_w, cur_h), pygame.RESIZABLE)

        TOP_BAR_HEIGHT = 48
        main_area_w = cur_w - 70
        main_area_h = cur_h - 90 - TOP_BAR_HEIGHT

        total_w_weight = sum(grid_weights_w)
        available_w = main_area_w - 20
        col_widths = [int(available_w * (w / total_w_weight)) for w in grid_weights_w]

        total_h_weight = sum(grid_weights_h)
        available_h = main_area_h - 10
        row_heights = [int(available_h * (h / total_h_weight)) for h in grid_weights_h]

        col_x_coords = [60]
        for w in col_widths[:-1]:
            col_x_coords.append(col_x_coords[-1] + w + 10)

        row_y_coords = [10 + TOP_BAR_HEIGHT]
        for h in row_heights[:-1]:
            row_y_coords.append(row_y_coords[-1] + h + 10)

        def get_module_rect(c, r, sw, sh):
            x = col_x_coords[c]
            y = row_y_coords[r]
            
            w = 0
            for i in range(sw):
                if c + i < len(col_widths):
                    w += col_widths[c + i]
            w += (sw - 1) * 10

            h = 0
            for j in range(sh):
                if r + j < len(row_heights):
                    h += row_heights[r + j]
            h += (sh - 1) * 10

            return pygame.Rect(x, y, w, h)

        module_rects = {}
        resize_handle_rects = {}
        detach_btn_rects = {}
        grid_divider_rects_v = []
        grid_divider_rects_h = []

        for mod_id, data in module_layouts.items():
            m_rect = get_module_rect(data["col"], data["row"], data["span_w"], data["span_h"])
            module_rects[mod_id] = m_rect
            resize_handle_rects[mod_id] = pygame.Rect(m_rect.right - 16, m_rect.bottom - 16, 16, 16)
            detach_btn_rects[mod_id] = pygame.Rect(m_rect.right - 42, m_rect.y + 10, 28, 28)

        if edit_layout_mode:
            for i in range(len(col_widths) - 1):
                div_x = col_x_coords[i] + col_widths[i]
                grid_divider_rects_v.append((i, pygame.Rect(div_x, 10 + TOP_BAR_HEIGHT, 10, main_area_h)))
            
            for j in range(len(row_heights) - 1):
                div_y = row_y_coords[j] + row_heights[j]
                grid_divider_rects_h.append((j, pygame.Rect(60, div_y, main_area_w, 10)))

        control_bar_rect = pygame.Rect(60, cur_h - 70, cur_w - 70, 60)
        
        root_minecraft_folder_btn = pygame.Rect(60, cur_h - 70, 48, 60)
        dropdown_rect = pygame.Rect(root_minecraft_folder_btn.right + 10, cur_h - 70, int(control_bar_rect.width * 0.32), 60)
        modpack_folder_btn = pygame.Rect(dropdown_rect.right + 10, cur_h - 70, 48, 60)
        create_version_btn = pygame.Rect(modpack_folder_btn.right + 10, cur_h - 70, 48, 60)
        edit_version_btn = pygame.Rect(create_version_btn.right + 10, cur_h - 70, 48, 60)
        launch_btn_rect = pygame.Rect(edit_version_btn.right + 10, cur_h - 70, (cur_w - 10) - (edit_version_btn.right + 10), 60)

        # Левая фиксированная панель 50px. Она заменяет навигацию из старого верхнего левого модуля.
        sidebar_rect = pygame.Rect(0, 0, 50, cur_h)
        sidebar_profile_btn = pygame.Rect(5, 55, 40, 40)
        sidebar_settings_btn = pygame.Rect(5, 105, 40, 40)
        sidebar_files_btn = pygame.Rect(5, 155, 40, 40)
        sidebar_update_btn = pygame.Rect(5, 205, 40, 40)
        sidebar_networks_btn = pygame.Rect(5, 255, 40, 40)

        # Панель профилей/никнеймов в верхнем левом модуле.
        nickname_dropdown_rect = pygame.Rect(0, 0, 0, 0)

        add_nickname_btn = pygame.Rect(0, 0, 0, 0)
        nickname_items = []
        nickname_delete_btns = {}
        nickname_plus_btns = {}
        nickname_build_menu_rect = pygame.Rect(0, 0, 0, 0)
        if "left" in module_rects and "left" not in detached_modules:
            l_r = module_rects["left"]

            nickname_dropdown_rect = pygame.Rect(l_r.x + 15, l_r.y + 48, l_r.width - 30, 44)
            add_nickname_btn = pygame.Rect(l_r.x + 15, l_r.bottom - 52, l_r.width - 30, 38)
            row_y = nickname_dropdown_rect.bottom + 5
            for nick in list(nickname_profiles.keys()):
                item = pygame.Rect(l_r.x + 15, row_y, l_r.width - 30, 38)
                nickname_items.append((nick, item))
                nickname_delete_btns[nick] = pygame.Rect(item.right - 34, item.y + 4, 30, 30)
                nickname_plus_btns[nick] = pygame.Rect(item.right - 70, item.y + 4, 30, 30)
                row_y += 42
            if nickname_build_menu_open and nickname_build_target in nickname_profiles:
                nickname_build_menu_rect = pygame.Rect(l_r.x + 15, nickname_dropdown_rect.bottom + 5, l_r.width - 30, min(220, max(1, len(versions)) * 34 + 8))

        profile_btn_rect = nav_main_btn = nav_mods_btn = nav_settings_btn = pygame.Rect(0, 0, 0, 0)

        if "right" in module_rects and "right" not in detached_modules:
            r_r = module_rects["right"]
            skin_preview_box = pygame.Rect(r_r.x + 15, r_r.y + 40, r_r.width - 30, max(60, r_r.height - 135))
            change_skin_btn = pygame.Rect(r_r.x + 15, r_r.bottom - 85, r_r.width - 30, 36)
            reset_skin_btn = pygame.Rect(r_r.x + 15, r_r.bottom - 42, r_r.width - 30, 32)
        else:
            skin_preview_box = change_skin_btn = reset_skin_btn = pygame.Rect(0, 0, 0, 0)

        settings_back_btn = pygame.Rect(60, 65, 180, 38)
        settings_sidebar_rect = pygame.Rect(60, 115, 250, cur_h - 130)
        settings_content_rect = pygame.Rect(settings_sidebar_rect.right + 10, 115, max(700, cur_w - settings_sidebar_rect.width - 60), cur_h - 130)

        set_tab_general_btn = pygame.Rect(settings_sidebar_rect.x + 10, settings_sidebar_rect.y + 15, settings_sidebar_rect.width - 20, 44)
        set_tab_appearance_btn = pygame.Rect(settings_sidebar_rect.x + 10, settings_sidebar_rect.y + 69, settings_sidebar_rect.width - 20, 44)

        settings_apply_btn = pygame.Rect(settings_content_rect.right - 230, settings_content_rect.bottom - 55, 200, 40)
        settings_cancel_btn = pygame.Rect(settings_apply_btn.x - 210, settings_content_rect.bottom - 55, 200, 40)

        settings_general_left_x = settings_content_rect.x + 30
        settings_general_right_x = settings_content_rect.x + 470

        ram_minus_btn = pygame.Rect(settings_general_right_x, settings_content_rect.y + 90, 40, 40)
        ram_plus_btn = pygame.Rect(settings_general_right_x + 170, settings_content_rect.y + 90, 40, 40)
        ram_protection_toggle_btn = pygame.Rect(settings_general_right_x, settings_content_rect.y + 140, 400, 36)
        action_toggle_btn = pygame.Rect(settings_general_right_x, settings_content_rect.y + 240, 400, 40)
        auto_backup_btn = pygame.Rect(settings_general_right_x, settings_content_rect.y + 295, 400, 40)

        language_dropdown_rect = pygame.Rect(settings_general_right_x, settings_content_rect.y + 370, 300, 36)
        lang_drop_menu_rect = pygame.Rect(language_dropdown_rect.x, language_dropdown_rect.bottom + 4, language_dropdown_rect.width, 108)

        scale_buttons = {
            0.8: pygame.Rect(settings_general_left_x, settings_content_rect.y + 60, 135, 32),
            1.0: pygame.Rect(settings_general_left_x + 150, settings_content_rect.y + 60, 135, 32),
            1.25: pygame.Rect(settings_general_left_x, settings_content_rect.y + 100, 135, 32),
            1.5: pygame.Rect(settings_general_left_x + 150, settings_content_rect.y + 100, 135, 32),
        }

        check_updates_btn = pygame.Rect(settings_general_left_x, settings_content_rect.y + 140, 300, 32)
        topmost_toggle_btn = pygame.Rect(settings_general_left_x, settings_content_rect.y + 200, 400, 32)
        incompatible_toggle_btn = pygame.Rect(settings_general_left_x, settings_content_rect.y + 240, 400, 32)
        updates_start_toggle_btn = pygame.Rect(settings_general_left_x, settings_content_rect.y + 280, 400, 32)
        sound_toggle_btn = pygame.Rect(settings_general_left_x, settings_content_rect.y + 320, 400, 32)
        error_log_toggle_btn = pygame.Rect(settings_general_left_x, settings_content_rect.y + 360, 400, 32)
        auto_start_toggle_btn = pygame.Rect(settings_general_left_x, settings_content_rect.y + 400, 400, 32)

        theme_dark_btn = pygame.Rect(settings_content_rect.x + 30, settings_content_rect.y + 95, 190, 40)
        theme_light_btn = pygame.Rect(settings_content_rect.x + 240, settings_content_rect.y + 95, 190, 40)
        picker_rect = pygame.Rect(settings_content_rect.x + 30, settings_content_rect.y + 230, PICKER_SIZE + 20, PICKER_SIZE + 20)
        
        bg_none_btn = pygame.Rect(settings_content_rect.x + 30, settings_content_rect.y + 250, 240, 36)
        bg_custom_btn = pygame.Rect(settings_content_rect.x + 290, settings_content_rect.y + 250, 240, 36)
        
        toggle_edit_layout_btn = pygame.Rect(settings_content_rect.x + 30, settings_content_rect.y + 440, 360, 42)
        
        mods_back_btn = pygame.Rect(60, 65, 120, 38)
        mods_top_panel = pygame.Rect(60, 115, cur_w - 30, 80)
        mods_list_rect = pygame.Rect(60, 205, cur_w - 30, cur_h - 220)
        
        modrinth_search_rect = pygame.Rect(mods_top_panel.x + 15, mods_top_panel.y + 20, 330, 40)
        modrinth_install_btn = pygame.Rect(modrinth_search_rect.right + 15, mods_top_panel.y + 20, 210, 40)
        
        mods_folder_btn = pygame.Rect(mods_top_panel.right - 100, mods_top_panel.y + 20, 40, 40)
        mods_copy_btn = pygame.Rect(mods_folder_btn.left - 70, mods_top_panel.y + 20, 40, 40)

        # Scanning the versions and mods folders every frame causes needless disk
        # activity. A short refresh interval keeps the UI responsive to external
        # changes while avoiding up to 60 directory scans per second.
        now = time.monotonic()
        if now >= content_refresh_at:
            previous_ver = cur_ver
            versions = sort_versions_with_favorites(get_installed_versions())
            if previous_ver in versions:
                selected_ver_idx = versions.index(previous_ver)
            elif selected_ver_idx >= len(versions):
                selected_ver_idx = len(versions) - 1
            cur_ver = versions[selected_ver_idx] if selected_ver_idx >= 0 else ""
            mods_dir_path = os.path.join(MINECRAFT_DIR, "versions", cur_ver, "mods") if cur_ver else ""
            local_mods = []
            if mods_dir_path and os.path.exists(mods_dir_path):
                local_mods = [f for f in os.listdir(mods_dir_path) if f.endswith(".jar") or f.endswith(".jar.disabled")]
            content_refresh_at = now + CONTENT_REFRESH_SECONDS

        def load_browser_page(reset=False):
            global cached_mod_results, mod_browser_api_offset, mod_browser_total_hits, mod_browser_is_loading_more, last_browser_search_query, mod_browser_scroll_offset
            query_text = (mod_browser_search_text or "").strip()
            pack_info = get_modpack_compatibility(cur_ver)
            version_value = get_browser_filter_value("version", pack_info.get("minecraft_version") or cur_ver or "1.20.1") or (pack_info.get("minecraft_version") or cur_ver or "1.20.1")
            loader_value = (get_browser_filter_value("loader", pack_info.get("loader") or "fabric") or pack_info.get("loader") or "fabric").lower()
            sort_value = bool(get_browser_filter_value("sort_asc", True))
            if shared_filter_dict is not None:
                shared_filter_dict["version"] = version_value
                shared_filter_dict["loader"] = loader_value
                shared_filter_dict["sort_asc"] = sort_value
            query_key = (query_text, version_value, loader_value, sort_value)

            if reset:
                cached_mod_results = []
                mod_browser_api_offset = 0
                mod_browser_total_hits = 0
                mod_browser_scroll_offset = 0
                last_browser_search_query = None

            if mod_browser_is_loading_more:
                return

            if reset or query_key != last_browser_search_query:
                last_browser_search_query = query_key
                mod_browser_is_loading_more = True
                threading.Thread(
                    target=search_modrinth_projects_async,
                    args=(
                        query_key, query_text, version_value, loader_value,
                        bool(sort_value), mod_browser_page_size, 0, True,
                    ),
                    daemon=True,
                ).start()
                return

            if mod_browser_api_offset >= mod_browser_total_hits:
                return

            mod_browser_is_loading_more = True
            threading.Thread(
                target=search_modrinth_projects_async,
                args=(
                    query_key, query_text, version_value, loader_value,
                    bool(sort_value), mod_browser_page_size, mod_browser_api_offset, False,
                ),
                daemon=True,
            ).start()

        def load_rp_browser_page(reset=False):
            global cached_rp_results, rp_browser_api_offset, rp_browser_total_hits, rp_browser_is_loading_more, last_rp_browser_search_query, rp_browser_scroll_offset
            pack_info = get_modpack_compatibility(cur_ver)
            mc_version = pack_info.get("minecraft_version", "")
            query_text = (rp_browser_search_text or "").strip()
            query_key = (query_text, mc_version)

            if reset:
                cached_rp_results = []
                rp_browser_api_offset = 0
                rp_browser_total_hits = 0
                rp_browser_scroll_offset = 0
                last_rp_browser_search_query = None

            if not mc_version:
                last_rp_browser_search_query = query_key
                return
            if rp_browser_is_loading_more:
                return

            if reset or query_key != last_rp_browser_search_query:
                last_rp_browser_search_query = query_key
                rp_browser_is_loading_more = True
                threading.Thread(
                    target=search_resource_packs_async,
                    args=(query_key, query_text, mc_version, rp_browser_page_size, 0, True),
                    daemon=True,
                ).start()
                return

            if len(cached_rp_results) >= rp_browser_max_cached:
                return
            if len(cached_rp_results) == 0:
                return

            rp_browser_is_loading_more = True
            threading.Thread(
                target=search_resource_packs_async,
                args=(query_key, query_text, mc_version, rp_browser_page_size, rp_browser_api_offset, False),
                daemon=True,
            ).start()

        if center_active_tab == "resourcepacks" and current_page == "main" and "center" in module_layouts and "center" not in detached_modules and not rp_browser_is_loading_more:
            if last_rp_browser_search_query is None:
                load_rp_browser_page(reset=True)

        # Large/fullscreen views show two normal result pages at once.
        is_large_view = cur_w >= 1500 or cur_h >= 900
        desired_page_size = 16 if is_large_view else 8
        if mod_browser_page_size != desired_page_size:
            mod_browser_page_size = desired_page_size
            if center_active_tab == "browser":
                last_browser_search_query = None
        if center_active_tab == "browser" and current_page == "main" and "center" in module_layouts and "center" not in detached_modules and not mod_browser_is_loading_more:
            browser_query = (
                (mod_browser_search_text or "").strip(),
                get_browser_filter_value("version", cur_ver or "1.20.1") or (cur_ver or "1.20.1"),
                (get_browser_filter_value("loader", "fabric") or "fabric").lower(),
                bool(get_browser_filter_value("sort_asc", True)),
            )
            if last_browser_search_query is None:
                load_browser_page(reset=True)

        if mod_browser_scroll_repeat_dir and current_page == "main" and "center" in module_layouts and "center" not in detached_modules and center_active_tab == "browser":
            max_b_scroll = max(0, len(cached_mod_results) * 65 - max(1, module_rects["center"].height - 152))
            if max_b_scroll > 0:
                now = time.monotonic()
                if now - mod_browser_scroll_repeat_started >= 0.12:
                    mod_browser_scroll_offset += mod_browser_scroll_repeat_dir * 18
                    mod_browser_scroll_offset = max(0, min(mod_browser_scroll_offset, max_b_scroll))
                    mod_browser_scroll_repeat_started = now

        if rp_browser_scroll_repeat_dir and current_page == "main" and "center" in module_layouts and "center" not in detached_modules and center_active_tab == "resourcepacks":
            max_rp_scroll = max(0, len(cached_rp_results) * 65 - max(1, module_rects["center"].height - 152))
            if max_rp_scroll > 0:
                now = time.monotonic()
                if now - rp_browser_scroll_repeat_started >= 0.12:
                    rp_browser_scroll_offset += rp_browser_scroll_repeat_dir * 18
                    rp_browser_scroll_offset = max(0, min(rp_browser_scroll_offset, max_rp_scroll))
                    rp_browser_scroll_repeat_started = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                for p in active_processes.values():
                    if p.is_alive():
                        p.terminate()
                save_config(username, cur_ver)
                pygame.quit()
                sys.exit()

            elif event.type == pygame.VIDEORESIZE:
                new_w = max(event.w, MIN_WIDTH)
                new_h = max(event.h, MIN_HEIGHT)
                screen = pygame.display.set_mode((new_w, new_h), pygame.RESIZABLE)

            elif event.type == pygame.MOUSEWHEEL:
                if dropdown_open:
                    versions_scroll_offset -= event.y * 30
                    max_scroll = max(0, len(versions) * 45 - 200)
                    versions_scroll_offset = max(0, min(versions_scroll_offset, max_scroll))
                elif current_page == "mods":
                    mods_scroll_offset -= event.y * 40
                    filtered_count = len([
                        m for m in local_mods
                        if not downloaded_mod_search_text.strip()
                        or downloaded_mod_search_text.lower() in m.lower()
                    ])
                    max_mod_scroll = max(0, filtered_count * 55 - (mods_list_rect.height - 20))
                    mods_scroll_offset = max(0, min(mods_scroll_offset, max_mod_scroll))
                elif current_page == "main" and "center" in module_layouts and "center" not in detached_modules and center_active_tab == "downloaded":
                    downloaded_mod_scroll_offset -= event.y * 40
                    filtered_count = len([m for m in local_mods if not downloaded_mod_search_text.strip() or downloaded_mod_search_text.lower() in m.lower()])
                    max_downloaded_scroll = max(0, filtered_count * 55 - (module_rects["center"].height - 140))
                    downloaded_mod_scroll_offset = max(0, min(downloaded_mod_scroll_offset, max_downloaded_scroll))
                elif current_page == "main" and "center" in module_layouts and "center" not in detached_modules and center_active_tab in ("browser", "resourcepacks"):
                    if not event.y == 0:
                        center_rect = module_rects["center"]
                        results_height = max(1, center_rect.height - 152)
                        if center_active_tab == "browser":
                            mod_browser_scroll_offset -= event.y * 40
                            max_b_scroll = max(0, len(cached_mod_results) * 65 - results_height)
                            mod_browser_scroll_offset = max(0, min(mod_browser_scroll_offset, max_b_scroll))
                            if mod_browser_api_offset < mod_browser_total_hits and not mod_browser_is_loading_more and mod_browser_scroll_offset > max(0, max_b_scroll * 0.8):
                                load_browser_page()
                        else:
                            rp_browser_scroll_offset -= event.y * 40
                            max_rp_scroll = max(0, len(cached_rp_results) * 65 - results_height)
                            rp_browser_scroll_offset = max(0, min(rp_browser_scroll_offset, max_rp_scroll))
                            if len(cached_rp_results) >= rp_browser_page_size and not rp_browser_is_loading_more and rp_browser_scroll_offset > max(0, max_rp_scroll * 0.8):
                                load_rp_browser_page()
                elif current_page == "main" and "console" in module_layouts and "console" not in detached_modules:
                    if not event.y == 0:
                        current_console_logs = get_live_logs()
                        console_rect = module_rects["console"]
                        max_visible_lines = max(2, (console_rect.height - 40) // 18)
                        max_scroll = max(0, len(current_console_logs) - max_visible_lines)
                        console_scroll_offset = max(0, min(console_scroll_offset + int(-event.y * 2), max_scroll))

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if current_page == "main" and "console" in module_layouts and "console" not in detached_modules:
                    console_rect = module_rects["console"]
                    console_box = pygame.Rect(console_rect.x + 12, console_rect.y + 35, console_rect.width - 24, console_rect.height - 47)
                    copy_btn = pygame.Rect(console_box.right - 96, console_box.y + 8, 84, 22)
                    scroll_track = pygame.Rect(console_box.right - 14, console_box.y + 8, 6, console_box.height - 16)
                    if copy_btn.collidepoint(event.pos):
                        copy_to_clipboard("\n".join(get_live_logs()))
                        add_log("[UI] Скопирован лог консоли.")
                        continue
                    if scroll_track.collidepoint(event.pos):
                        log_lines = get_live_logs()
                        max_visible_lines = max(2, (console_box.height - 40) // 18)
                        max_scroll = max(0, len(log_lines) - max_visible_lines)
                        if max_scroll > 0:
                            ratio = max(0.0, min(1.0, (event.pos[1] - scroll_track.y) / max(1, scroll_track.height)))
                            console_scroll_offset = int(ratio * max_scroll)
                        continue

                if root_minecraft_folder_btn.collidepoint(event.pos):
                    open_folder(MINECRAFT_DIR)
                    add_log(f"[Folders] Відкрито головну папку Minecraft: {MINECRAFT_DIR}")

                elif modpack_folder_btn.collidepoint(event.pos):
                    if cur_ver:
                        modpack_dir = os.path.join(MINECRAFT_DIR, "versions", cur_ver)
                    else:
                        modpack_dir = os.path.join(MINECRAFT_DIR, "versions")
                    open_folder(modpack_dir)
                    add_log(f"[Folders] Відкрито папку модпака/версії: {cur_ver}")

                elif create_version_btn.collidepoint(event.pos):
                    add_log("[UI] Відкрито вікно створення нової версії.")
                    p_create = multiprocessing.Process(
                        target=run_version_creator_process,
                        args=(current_theme, shared_logs_manager)
                    )
                    p_create.start()

                elif edit_version_btn.collidepoint(event.pos) and cur_ver and not running_state:
                    add_log(f"[UI] Відкрито редактор версії: {cur_ver}")
                    p_edit = multiprocessing.Process(
                        target=run_version_editor_process,
                        args=(current_theme, cur_ver, shared_logs_manager)
                    )
                    p_edit.start()
                    p_edit.join()
                    versions = get_installed_versions()
                    if cur_ver in versions:
                        selected_ver_idx = versions.index(cur_ver)
                    elif versions:
                        selected_ver_idx = min(selected_ver_idx, len(versions) - 1)
                    else:
                        selected_ver_idx = -1
                    dropdown_open = False
                    add_log("[UI] Редактор версии закрыт. Список версий обновлён.")

                if current_page == "main" and not edit_layout_mode:
                    detached_action_triggered = False
                    for mod_id, d_btn in detach_btn_rects.items():
                        if d_btn.collidepoint(event.pos):
                            if mod_id in detached_modules:
                                if mod_id in active_processes:
                                    active_processes[mod_id].terminate()
                                    del active_processes[mod_id]
                                detached_modules.remove(mod_id)
                                add_log(f"[UI] Модуль '{mod_id}' возвращен на сетку.")
                            else:
                                detached_modules.append(mod_id)
                                bg_c_pass = {
                                    "mode": bg_mode,
                                    "preset": bg_preset,
                                    "custom_path": bg_custom_path,
                                    "color": bg_pattern_color
                                }
                                p = multiprocessing.Process(
                                    target=run_detached_module_process,
                                    args=(mod_id, current_theme, skin_path, shared_logs_manager, bg_c_pass)
                                )
                                p.start()
                                active_processes[mod_id] = p
                                add_log(f"[UI] Модуль '{mod_id}' открыт в отдельном окне.")
                            
                            detached_action_triggered = True
                            break
                    if detached_action_triggered:
                        continue

                    # Проверка кликов по центру: Новости / Модпаки / Моды / Ресурс-паки
                    if "center" in module_rects and "center" not in detached_modules:
                        c_rect = module_rects["center"]
                        tab_y = c_rect.y + 35
                        tab_gap = 5
                        tab_w = max(64, int((c_rect.width - 30 - tab_gap * 3) / 4))
                        tab_news_rect = pygame.Rect(c_rect.x + 15, tab_y, tab_w, 30)
                        tab_downloaded_rect = pygame.Rect(tab_news_rect.right + tab_gap, tab_y, tab_w, 30)
                        tab_browser_rect = pygame.Rect(tab_downloaded_rect.right + tab_gap, tab_y, tab_w, 30)
                        tab_rp_rect = pygame.Rect(tab_browser_rect.right + tab_gap, tab_y, tab_w, 30)

                        if tab_news_rect.collidepoint(event.pos):
                            center_active_tab = "news"
                        elif tab_downloaded_rect.collidepoint(event.pos):
                            center_active_tab = "downloaded"
                            downloaded_mod_search_active = False
                            downloaded_mod_search_text = ""
                            downloaded_mod_scroll_offset = 0
                            current_page = "mods"
                            continue
                        elif tab_browser_rect.collidepoint(event.pos):
                            center_active_tab = "browser"
                            last_browser_search_query = None
                            load_browser_page(reset=True)
                        elif tab_rp_rect.collidepoint(event.pos):
                            center_active_tab = "resourcepacks"
                            last_rp_browser_search_query = None
                            load_rp_browser_page(reset=True)

                        if center_active_tab == "downloaded":
                            search_box_rect = pygame.Rect(c_rect.x + 15, c_rect.y + 75, c_rect.width - 130, 36)
                            folder_btn_rect = pygame.Rect(search_box_rect.right + 10, c_rect.y + 75, 95, 36)
                            if search_box_rect.collidepoint(event.pos):
                                downloaded_mod_search_active = True
                            else:
                                downloaded_mod_search_active = False
                            if folder_btn_rect.collidepoint(event.pos):
                                open_folder(mods_dir_path)
                            elif not search_box_rect.collidepoint(event.pos):
                                downloaded_clip = pygame.Rect(c_rect.x + 10, c_rect.y + 130, c_rect.width - 20, c_rect.height - 140)
                                filtered_mods = [m for m in local_mods if not downloaded_mod_search_text.strip() or downloaded_mod_search_text.lower() in m.lower()]
                                clicked_y = event.pos[1] - downloaded_clip.y + downloaded_mod_scroll_offset
                                idx = int(clicked_y // 55)
                                if downloaded_clip.collidepoint(event.pos) and 0 <= idx < len(filtered_mods):
                                    mod_file = filtered_mods[idx]
                                    mod_path = os.path.join(mods_dir_path, mod_file)
                                    item_y = downloaded_clip.y + idx * 55 - downloaded_mod_scroll_offset
                                    item_r = pygame.Rect(downloaded_clip.x, item_y, downloaded_clip.width - 8, 48)
                                    toggle_r = pygame.Rect(item_r.right - 170, item_r.y + 9, 76, 30)
                                    del_r = pygame.Rect(item_r.right - 86, item_r.y + 9, 76, 30)
                                    if del_r.collidepoint(event.pos):
                                        try: os.remove(mod_path)
                                        except Exception as exc: print(f"Ошибка удаления мода: {exc}")
                                    elif toggle_r.collidepoint(event.pos):
                                        try:
                                            new_name = mod_file.replace(".disabled", "") if mod_file.endswith(".disabled") else mod_file + ".disabled"
                                            os.rename(mod_path, os.path.join(mods_dir_path, new_name))
                                        except Exception as exc: print(f"Ошибка переключения мода: {exc}")
                        elif center_active_tab in ("browser", "resourcepacks"):
                            is_rp = center_active_tab == "resourcepacks"
                            search_box_rect = pygame.Rect(c_rect.x + 15, c_rect.y + 75, c_rect.width - 130, 36)
                            filter_btn_rect = pygame.Rect(search_box_rect.right + 10, c_rect.y + 75, 95, 36)
                            results_clip_rect = pygame.Rect(c_rect.x + 10, c_rect.y + 55, c_rect.width - 60, c_rect.height - 65)
                            browser_scroll_track = pygame.Rect(results_clip_rect.right + 6, results_clip_rect.y + 12, 14, max(40, results_clip_rect.height - 24))
                            result_count = len(cached_rp_results) if is_rp else len(cached_mod_results)
                            current_scroll = rp_browser_scroll_offset if is_rp else mod_browser_scroll_offset
                            max_b_scroll = max(0, result_count * 65 - results_clip_rect.height)

                            browser_scroll_thumb = pygame.Rect(
                                browser_scroll_track.x,
                                browser_scroll_track.y,
                                browser_scroll_track.width,
                                max(28, int(browser_scroll_track.height * (results_clip_rect.height / max(1, result_count * 65))))
                            )
                            if max_b_scroll > 0:
                                browser_scroll_thumb.y = browser_scroll_track.y + int((current_scroll / max_b_scroll) * max(1, browser_scroll_track.height - browser_scroll_thumb.height))

                            if search_box_rect.collidepoint(event.pos):
                                if is_rp:
                                    rp_browser_search_active = True
                                else:
                                    mod_browser_search_active = True
                            else:
                                mod_browser_search_active = False
                                rp_browser_search_active = False

                            if filter_btn_rect.collidepoint(event.pos) and not is_rp:
                                load_browser_page(reset=True)
                            elif not search_box_rect.collidepoint(event.pos):
                                browser_scroll_up_btn = pygame.Rect(browser_scroll_track.x - 2, browser_scroll_track.y - 18, browser_scroll_track.width + 4, 16)
                                browser_scroll_down_btn = pygame.Rect(browser_scroll_track.x - 2, browser_scroll_track.bottom + 2, browser_scroll_track.width + 4, 16)
                                if browser_scroll_up_btn.collidepoint(event.pos):
                                    if is_rp:
                                        rp_browser_scroll_repeat_dir = -1
                                        rp_browser_scroll_repeat_started = time.monotonic()
                                        rp_browser_scroll_offset = max(0, rp_browser_scroll_offset - 18)
                                    else:
                                        mod_browser_scroll_repeat_dir = -1
                                        mod_browser_scroll_repeat_started = time.monotonic()
                                        mod_browser_scroll_offset = max(0, mod_browser_scroll_offset - 18)
                                elif browser_scroll_down_btn.collidepoint(event.pos):
                                    if is_rp:
                                        rp_browser_scroll_repeat_dir = 1
                                        rp_browser_scroll_repeat_started = time.monotonic()
                                        rp_browser_scroll_offset = min(max_b_scroll, rp_browser_scroll_offset + 18)
                                    else:
                                        mod_browser_scroll_repeat_dir = 1
                                        mod_browser_scroll_repeat_started = time.monotonic()
                                        mod_browser_scroll_offset = min(max_b_scroll, mod_browser_scroll_offset + 18)
                                elif browser_scroll_track.collidepoint(event.pos) or browser_scroll_thumb.collidepoint(event.pos):
                                    is_dragging_browser_scrollbar = True
                                    if max_b_scroll > 0:
                                        travel = max(1, browser_scroll_track.height - browser_scroll_thumb.height)
                                        ratio = (event.pos[1] - browser_scroll_track.y - browser_scroll_thumb.height / 2) / travel
                                        ratio = max(0.0, min(1.0, ratio))
                                        if is_rp:
                                            rp_browser_scroll_offset = int(ratio * max_b_scroll)
                                        else:
                                            mod_browser_scroll_offset = int(ratio * max_b_scroll)
                                else:
                                    if is_rp:
                                        visible_start = int(rp_browser_scroll_offset // 65)
                                        visible_end = min(len(cached_rp_results), visible_start + max(1, (results_clip_rect.height // 65) + 3))
                                        pack_info = get_modpack_compatibility(cur_ver)
                                        target_mc = pack_info.get("minecraft_version", "")
                                        target_rp_dir = get_target_resourcepacks_dir(cur_ver) if cur_ver else ""
                                        for idx in range(visible_start, visible_end):
                                            item = cached_rp_results[idx]
                                            item_rect = pygame.Rect(c_rect.x + 15, c_rect.y + 125 + (idx * 65) - rp_browser_scroll_offset, c_rect.width - 120, 55)
                                            install_btn_rect = pygame.Rect(item_rect.right - 72, item_rect.y + 12, 62, 30)
                                            if install_btn_rect.collidepoint(event.pos):
                                                project_id = item.get("id") or item.get("project_id")
                                                if not cur_ver:
                                                    add_log("[RPBrowser] Сначала выберите мод-пак.")
                                                elif not target_mc:
                                                    add_log(f"[RPBrowser] Не удалось определить Minecraft-версию мод-пака '{cur_ver}'.")
                                                elif project_id:
                                                    if is_resource_pack_installed(project_id, target_rp_dir, target_mc):
                                                        add_log(f"[RPBrowser] Ресурс-пак {project_id} уже установлен.")
                                                    else:
                                                        threading.Thread(
                                                            target=install_resource_pack_for_profile,
                                                            args=(project_id, cur_ver),
                                                            daemon=True,
                                                        ).start()
                                                break
                                            elif item_rect.collidepoint(event.pos):
                                                break
                                    else:
                                        visible_start = int(mod_browser_scroll_offset // 65)
                                        visible_end = min(len(cached_mod_results), visible_start + max(1, (results_clip_rect.height // 65) + 3))
                                        for idx in range(visible_start, visible_end):
                                            mod_item = cached_mod_results[idx]
                                            item_rect = pygame.Rect(c_rect.x + 15, c_rect.y + 125 + (idx * 65) - mod_browser_scroll_offset, c_rect.width - 120, 55)
                                            install_btn_rect = pygame.Rect(item_rect.right - 72, item_rect.y + 12, 62, 30)
                                            if install_btn_rect.collidepoint(event.pos):
                                                slug = mod_item.get("slug")
                                                target_profile = cur_ver
                                                target_mods_dir = get_target_mods_dir(target_profile) if target_profile else mods_dir_path
                                                if slug and target_profile:
                                                    if is_mod_installed_by_slug(slug, target_mods_dir):
                                                        add_log(f"[ModBrowser] Мод {slug} уже установлен.")
                                                    else:
                                                        compatibility = get_modpack_compatibility(target_profile)
                                                        add_log(
                                                            f"[ModBrowser] Установка {slug} в мод-пак '{target_profile}': "
                                                            f"Minecraft={compatibility.get('minecraft_version') or '?'}; "
                                                            f"loader={compatibility.get('loader') or '?'}"
                                                        )
                                                        threading.Thread(
                                                            target=download_modrinth_project,
                                                            args=(slug, target_profile, target_mods_dir),
                                                            kwargs={"loader": None},
                                                            daemon=True,
                                                        ).start()
                                                break
                                            elif item_rect.collidepoint(event.pos):
                                                slug = mod_item.get("slug") or mod_item.get("id")
                                                if slug:
                                                    p = multiprocessing.Process(
                                                        target=run_mod_details_process,
                                                        args=(slug, shared_filter_dict.get("version", cur_ver), shared_filter_dict.get("loader", "fabric"), mods_dir_path, current_theme)
                                                    )
                                                    p.start()
                                                break

                if edit_layout_mode and current_page == "main":
                    for col_idx, d_rect in grid_divider_rects_v:
                        if d_rect.collidepoint(event.pos):
                            resizing_grid_col = col_idx
                            break
                    
                    if resizing_grid_col is None:
                        for row_idx, d_rect in grid_divider_rects_h:
                            if d_rect.collidepoint(event.pos):
                                resizing_grid_row = row_idx
                                break

                    if resizing_grid_col is None and resizing_grid_row is None:
                        for mod_id, h_rect in resize_handle_rects.items():
                            if h_rect.collidepoint(event.pos):
                                resizing_module = mod_id
                                break
                    
                    if resizing_grid_col is None and resizing_grid_row is None and not resizing_module:
                        for mod_id, r in module_rects.items():
                            if r.collidepoint(event.pos) and mod_id not in detached_modules:
                                dragged_module = mod_id
                                drag_offset_x = event.pos[0] - r.x
                                drag_offset_y = event.pos[1] - r.y
                                break

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                mod_browser_scroll_repeat_dir = 0
                rp_browser_scroll_repeat_dir = 0
                if dragged_module or resizing_module or resizing_grid_col is not None or resizing_grid_row is not None or is_dragging_scrollbar or is_dragging_mods_scrollbar or is_dragging_browser_scrollbar:
                    dragged_module = None
                    resizing_module = None
                    resizing_grid_col = None
                    resizing_grid_row = None
                    is_dragging_scrollbar = False
                    is_dragging_mods_scrollbar = False
                    is_dragging_browser_scrollbar = False
                    save_config(username, cur_ver)

            elif event.type == pygame.MOUSEMOTION:
                if is_dragging_scrollbar and dropdown_open:
                    menu_height = min(220, len(versions) * 45)
                    scroll_track_height = menu_height - 10
                    max_content_height = len(versions) * 45
                     
                    dy = event.rel[1]
                    scroll_ratio = dy / scroll_track_height
                    versions_scroll_offset += scroll_ratio * max_content_height
                    max_scroll = max(0, max_content_height - menu_height)
                    versions_scroll_offset = max(0, min(versions_scroll_offset, max_scroll))
                    
                elif is_dragging_mods_scrollbar and current_page == "mods":
                    visible_height = mods_list_rect.height - 20
                    max_content_height = len(local_mods) * 55
                    scroll_track_height = visible_height
                    
                    dy = event.rel[1]
                    scroll_ratio = dy / scroll_track_height
                    mods_scroll_offset += scroll_ratio * max_content_height
                    max_scroll = max(0, max_content_height - visible_height)
                    mods_scroll_offset = max(0, min(mods_scroll_offset, max_scroll))

                elif is_dragging_browser_scrollbar and current_page == "main" and center_active_tab in ("browser", "resourcepacks"):
                    results_clip_rect = pygame.Rect(module_rects["center"].x + 10, module_rects["center"].y + 55, module_rects["center"].width - 60, module_rects["center"].height - 65)
                    scroll_track = pygame.Rect(results_clip_rect.right + 6, results_clip_rect.y + 12, 14, max(40, results_clip_rect.height - 24))
                    result_count = len(cached_rp_results) if center_active_tab == "resourcepacks" else len(cached_mod_results)
                    max_b_scroll = max(0, result_count * 65 - results_clip_rect.height)
                    if max_b_scroll > 0:
                        thumb_h = max(28, int(scroll_track.height * (results_clip_rect.height / max(1, result_count * 65))))
                        thumb_h = min(scroll_track.height, thumb_h)
                        travel = max(1, scroll_track.height - thumb_h)
                        y_ratio = max(0.0, min(1.0, (event.pos[1] - scroll_track.y - thumb_h / 2) / travel))
                        if center_active_tab == "resourcepacks":
                            rp_browser_scroll_offset = int(y_ratio * max_b_scroll)
                        else:
                            mod_browser_scroll_offset = int(y_ratio * max_b_scroll)

                elif edit_layout_mode:
                    if resizing_grid_col is not None:
                        dx = event.rel[0]
                        total_w = sum(grid_weights_w)
                        factor = total_w / available_w
                        delta_weight = dx * factor
                        
                        grid_weights_w[resizing_grid_col] = max(0.4, grid_weights_w[resizing_grid_col] + delta_weight)
                        grid_weights_w[resizing_grid_col + 1] = max(0.4, grid_weights_w[resizing_grid_col + 1] - delta_weight)

                    elif resizing_grid_row is not None:
                        dy = event.rel[1]
                        total_h = sum(grid_weights_h)
                        factor = total_h / available_h
                        delta_weight = dy * factor
                        
                        grid_weights_h[resizing_grid_row] = max(0.4, grid_weights_h[resizing_grid_row] + delta_weight)
                        grid_weights_h[resizing_grid_row + 1] = max(0.4, grid_weights_h[resizing_grid_row + 1] - delta_weight)

                    elif dragged_module:
                        for c_idx, cx in enumerate(col_x_coords):
                            for r_idx, ry in enumerate(row_y_coords):
                                cell_r = pygame.Rect(cx, ry, col_widths[c_idx], row_heights[r_idx])
                                if cell_r.collidepoint(event.pos):
                                    module_layouts[dragged_module]["col"] = c_idx
                                    module_layouts[dragged_module]["row"] = r_idx
                                    break

                    elif resizing_module:
                        m_data = module_layouts[resizing_module]
                        base_x = col_x_coords[m_data["col"]]
                        base_y = row_y_coords[m_data["row"]]
                        rel_x = event.pos[0] - base_x
                        rel_y = event.pos[1] - base_y

                        span_w = 1
                        current_w_sum = 0
                        for i in range(m_data["col"], 3):
                            current_w_sum += col_widths[i] + 10
                            if rel_x >= current_w_sum - 20:
                                span_w = i - m_data["col"] + 1

                        span_h = 1
                        current_h_sum = 0
                        for j in range(m_data["row"], 2):
                            current_h_sum += row_heights[j] + 10
                            if rel_y >= current_h_sum - 20:
                                span_h = j - m_data["row"] + 1

                        m_data["span_w"] = max(1, min(3 - m_data["col"], span_w))
                        m_data["span_h"] = max(1, min(2 - m_data["row"], span_h))

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Цветовые пикеры работают как модальные окна: пока один открыт,
                # никакие кнопки под ним не получают клик.
                if current_page == "settings" and settings_tab == "appearance" and (color_picker_open or bg_color_picker_open):
                    active_picker_rect = (
                        pygame.Rect(settings_content_rect.x + 30, settings_content_rect.y + 230, PICKER_SIZE + 20, PICKER_SIZE + 20)
                        if color_picker_open else
                        pygame.Rect(settings_content_rect.x + 30, settings_content_rect.y + 410, PICKER_SIZE + 20, PICKER_SIZE + 20)
                    )
                    close_rect = pygame.Rect(active_picker_rect.x + 4, active_picker_rect.y + 4, 24, 24)

                    if close_rect.collidepoint(event.pos):
                        color_picker_open = False
                        bg_color_picker_open = False
                        continue

                    px_rel_x = event.pos[0] - (active_picker_rect.x + 10)
                    px_rel_y = event.pos[1] - (active_picker_rect.y + 10)
                    if 0 <= px_rel_x < PICKER_SIZE and 0 <= px_rel_y < PICKER_SIZE:
                        hue = px_rel_x / PICKER_SIZE
                        sat = 1.0 - (px_rel_y / PICKER_SIZE)
                        r, g, b = colorsys.hsv_to_rgb(hue, sat, 1.0)
                        picked_color = (int(r * 255), int(g * 255), int(b * 255))
                        if color_picker_open:
                            temp_custom_color = picked_color
                            temp_accent_idx = len(DEFAULT_PRESETS)
                        else:
                            temp_bg_pattern_color = picked_color
                    # Клик вне пикера тоже не проходит к элементам интерфейса.
                    continue

                if selected_ver_idx >= len(versions):
                    selected_ver_idx = max(0, len(versions) - 1)

                if current_page == "main" and not edit_layout_mode:
                    # --- Левая боковая панель ---
                    if sidebar_profile_btn.collidepoint(event.pos):
                        current_page = "main"
                    elif sidebar_settings_btn.collidepoint(event.pos):
                        current_page = "settings"
                        temp_theme = current_theme
                        temp_accent_idx = accent_idx
                        temp_custom_color = custom_color
                        temp_ram_gb = ram_gb
                        temp_ram_protection = ram_protection
                        temp_launch_action = launch_action
                        temp_auto_backup_enabled = auto_backup_enabled
                        temp_always_on_top = always_on_top
                        temp_auto_disable_incompatible_mods = auto_disable_incompatible_mods
                        temp_check_updates_on_start = check_updates_on_start
                        temp_sound_notifications = sound_notifications
                        temp_open_error_log_on_failed_launch = open_error_log_on_failed_launch
                        temp_auto_start = auto_start
                        temp_interface_scale = interface_scale
                        temp_ui_language = ui_language
                        temp_bg_mode = bg_mode
                        temp_bg_preset = bg_preset
                        temp_bg_custom_path = bg_custom_path
                        temp_bg_pattern_color = bg_pattern_color
                    elif sidebar_files_btn.collidepoint(event.pos):
                        open_folder(os.path.dirname(os.path.abspath(__file__)))
                    elif sidebar_update_btn.collidepoint(event.pos):
                        has_update, version = check_for_launcher_updates_now()
                        add_log(f"[Update] Обновление доступно: {version or 'archive'}" if has_update else "[Update] Обновления не найдены.")
                    elif sidebar_networks_btn.collidepoint(event.pos):
                        add_log("[Networks] Раздел социальных сетей пока готовит ссылки.")

                    # Создание никнейма.
                    if add_nickname_btn.collidepoint(event.pos):
                        nickname_input_active = True
                        nickname_input_text = ""
                        nickname_build_menu_open = False
                    elif nickname_input_active:
                        pass
                    else:
                        # Выбор/удаление/привязка сборки к никнейму.
                        handled_nickname = False
                        for nick, item_rect in nickname_items:
                            if nickname_delete_btns[nick].collidepoint(event.pos):
                                nickname_profiles.pop(nick, None)
                                if active_nickname == nick:
                                    if nickname_profiles:
                                        active_nickname = next(iter(nickname_profiles))
                                        username = active_nickname
                                        target = nickname_profiles.get(active_nickname, "")
                                        if target in versions:
                                            selected_ver_idx = versions.index(target)
                                            cur_ver = target
                                save_config(username, cur_ver)
                                handled_nickname = True
                                break
                            if nickname_plus_btns[nick].collidepoint(event.pos):
                                nickname_build_target = nick
                                nickname_build_menu_open = not nickname_build_menu_open
                                handled_nickname = True
                                break
                            if item_rect.collidepoint(event.pos):
                                active_nickname = nick
                                username = nick
                                target = nickname_profiles.get(nick, "")
                                if target in versions:
                                    selected_ver_idx = versions.index(target)
                                    cur_ver = target
                                    mods_dir_path = get_target_mods_dir(cur_ver)
                                    shared_filter_dict["version"] = cur_ver
                                save_config(username, cur_ver)
                                nickname_build_menu_open = False
                                handled_nickname = True
                                break
                        if nickname_build_menu_open and nickname_build_target:
                            for vi, vv in enumerate(versions):
                                build_item = pygame.Rect(nickname_build_menu_rect.x + 4, nickname_build_menu_rect.y + 4 + vi * 34, nickname_build_menu_rect.width - 8, 30)
                                if build_item.collidepoint(event.pos):
                                    nickname_profiles[nickname_build_target] = vv
                                    if active_nickname == nickname_build_target:
                                        username = nickname_build_target
                                        selected_ver_idx = vi
                                        cur_ver = vv
                                        mods_dir_path = get_target_mods_dir(cur_ver)
                                        shared_filter_dict["version"] = cur_ver
                                    save_config(username, cur_ver)
                                    nickname_build_menu_open = False
                                    handled_nickname = True
                                    break
                        if nickname_dropdown_rect.collidepoint(event.pos):
                            nickname_build_menu_open = not nickname_build_menu_open
                            handled_nickname = True


                    old_active = input_active
                    if "left" in module_rects and "left" not in detached_modules and profile_btn_rect.collidepoint(event.pos):
                        input_active = True
                    else:
                        input_active = False

                    if old_active and not input_active:
                        save_config(username, cur_ver)


                    if "right" in module_rects and "right" not in detached_modules:
                        if change_skin_btn.collidepoint(event.pos):
                            select_skin_dialog()
                            save_config(username, cur_ver)
                        elif reset_skin_btn.collidepoint(event.pos):
                            skin_path = ""
                            load_skin_file("")
                            save_config(username, cur_ver)
                            add_log("[Skin] Сброшен скин на стандартный.")

                    if dropdown_rect.collidepoint(event.pos) and not running_state:
                        dropdown_open = not dropdown_open
                        versions_scroll_offset = 0
                    elif dropdown_open:
                        menu_height = min(220, len(versions) * 45)
                        dropdown_list_rect = pygame.Rect(dropdown_rect.x, dropdown_rect.y - menu_height - 5, dropdown_rect.width, menu_height)
                        scrollbar_rect = pygame.Rect(dropdown_list_rect.right - 12, dropdown_list_rect.y + 5, 8, menu_height - 10)

                        if scrollbar_rect.collidepoint(event.pos):
                            is_dragging_scrollbar = True
                        elif dropdown_list_rect.collidepoint(event.pos):
                            clicked_y = event.pos[1] - (dropdown_list_rect.y + 5) + versions_scroll_offset
                            clicked_idx = int(clicked_y // 45)
                            if 0 <= clicked_idx < len(versions):
                                clicked_version = versions[clicked_idx]
                                item_y = dropdown_list_rect.y + 5 + clicked_idx * 45 - versions_scroll_offset
                                item_r = pygame.Rect(dropdown_list_rect.x + 5, item_y, dropdown_list_rect.width - 15, 40)
                                fav_btn = pygame.Rect(item_r.right - 34, item_r.y + 7, 28, 26)
                                if fav_btn.collidepoint(event.pos):
                                    toggle_version_favorite(clicked_version)
                                    current_version = cur_ver
                                    versions = sort_versions_with_favorites(get_installed_versions())
                                    if current_version in versions:
                                        selected_ver_idx = versions.index(current_version)
                                    save_config(username, cur_ver)
                                    continue

                                selected_ver_idx = clicked_idx
                                cur_ver = versions[selected_ver_idx]
                                mods_dir_path = get_target_mods_dir(cur_ver)
                                # Выбор сборки автоматически выбирает привязанный никнейм.
                                matching = [n for n, v in nickname_profiles.items() if v == cur_ver]
                                if matching:
                                    active_nickname = matching[0]
                                    username = active_nickname
                                elif active_nickname:
                                    nickname_profiles[active_nickname] = cur_ver
                                save_config(username, cur_ver)
                                shared_filter_dict["version"] = cur_ver
                                dropdown_open = False
                        else:
                            dropdown_open = False


                    if launch_btn_rect.collidepoint(event.pos):
                        if running_state:
                            stop_minecraft(log_func=add_log)
                        elif selected_ver_idx != -1 and not is_ui_activity_active("launch"):
                            save_config(username, cur_ver)
                            logs.clear()
                            if shared_logs_manager is not None:
                                shared_logs_manager[:] = []
                            add_log(f"[UI] Старт сессии {cur_ver} с RAM: {ram_gb}GB...")
                            
                            try:
                                set_ui_activity("launch", True)
                                threading.Thread(
                                    target=launch_minecraft_background,
                                    args=(username, cur_ver, ram_gb, add_log),
                                    daemon=True,
                                ).start()
                                close_after_launch = launch_action == "close"
                                continue
                                set_ui_activity("launch", False)

                                if launch_action == "close":
                                    pygame.quit()
                                    while is_game_running():
                                        pygame.time.wait(500)
                                    reopen_pygame_window(cur_w, cur_h)
                                    add_log("[System] Игра завершена. Лаунчер перезапущен.")
                            except Exception as e:
                                add_log(f"[ERROR] Ошибка запуска: {e}")

                elif current_page == "mods":
                    if mods_back_btn.collidepoint(event.pos):
                        current_page = "main"
                        downloaded_mod_search_active = False
                        downloaded_mod_scroll_offset = 0
                        continue

                    if modrinth_search_rect.collidepoint(event.pos):
                        downloaded_mod_search_active = True
                    else:
                        downloaded_mod_search_active = False

                    if mods_folder_btn.collidepoint(event.pos):
                        open_folder(mods_dir_path)

                    if mods_copy_btn.collidepoint(event.pos):
                        names = [f.replace(".disabled", "") for f in local_mods]
                        copy_to_clipboard("\n".join(names))
                        modrinth_download_status = "Названия модов скопированы!"

                    filtered_local_mods = [
                        m for m in local_mods
                        if not downloaded_mod_search_text.strip()
                        or downloaded_mod_search_text.lower() in m.lower()
                    ]

                    visible_mods_rect = pygame.Rect(mods_list_rect.x, mods_list_rect.y, mods_list_rect.width - 20, mods_list_rect.height)
                    if visible_mods_rect.collidepoint(event.pos):
                        clicked_y = event.pos[1] - mods_list_rect.y - 10 + mods_scroll_offset
                        clicked_idx = int(clicked_y // 55)
                        if 0 <= clicked_idx < len(filtered_local_mods):
                            mod_file = filtered_local_mods[clicked_idx]
                            mod_path = os.path.join(mods_dir_path, mod_file)
                            item_y_actual = mods_list_rect.y + 10 + clicked_idx * 55 - mods_scroll_offset
                            del_btn = pygame.Rect(mods_list_rect.right - 100, item_y_actual + 10, 80, 30)
                            toggle_btn = pygame.Rect(mods_list_rect.right - 190, item_y_actual + 10, 80, 30)
                            if del_btn.collidepoint(event.pos):
                                try:
                                    os.remove(mod_path)
                                except Exception as e:
                                    print(f"Помилка видалення: {e}")
                            elif toggle_btn.collidepoint(event.pos):
                                try:
                                    new_name = mod_file.replace(".disabled", "") if mod_file.endswith(".disabled") else mod_file + ".disabled"
                                    os.rename(mod_path, os.path.join(mods_dir_path, new_name))
                                except Exception as e:
                                    print(f"Помилка перейменування: {e}")

                    max_mod_scroll = max(0, len(filtered_local_mods) * 55 - (mods_list_rect.height - 20))
                    mods_scroll_offset = max(0, min(mods_scroll_offset, max_mod_scroll))
                    if max_mod_scroll > 0:
                        mods_scrollbar_track = pygame.Rect(mods_list_rect.right - 12, mods_list_rect.y + 5, 8, mods_list_rect.height - 10)
                        if mods_scrollbar_track.collidepoint(event.pos):
                            is_dragging_mods_scrollbar = True
                elif current_page == "settings":
                    language_dropdown_open = locals().get("language_dropdown_open", False)
                    if settings_back_btn.collidepoint(event.pos):
                        current_page = "main"
                        color_picker_open = False
                        bg_color_picker_open = False
                        language_dropdown_open = False

                    if set_tab_general_btn.collidepoint(event.pos):
                        settings_tab = "general"
                        color_picker_open = False
                        bg_color_picker_open = False
                    elif set_tab_appearance_btn.collidepoint(event.pos):
                        settings_tab = "appearance"

                    if settings_apply_btn.collidepoint(event.pos):
                        current_theme = temp_theme
                        accent_idx = temp_accent_idx
                        custom_color = temp_custom_color
                        ram_gb = temp_ram_gb
                        ram_protection = temp_ram_protection
                        launch_action = temp_launch_action
                        auto_backup_enabled = temp_auto_backup_enabled
                        always_on_top = temp_always_on_top
                        auto_disable_incompatible_mods = temp_auto_disable_incompatible_mods
                        check_updates_on_start = temp_check_updates_on_start
                        sound_notifications = temp_sound_notifications
                        open_error_log_on_failed_launch = temp_open_error_log_on_failed_launch
                        auto_start = temp_auto_start
                        interface_scale = temp_interface_scale
                        ui_language = temp_ui_language
                        translator.set_language(ui_language)
                        bg_mode = temp_bg_mode
                        bg_preset = temp_bg_preset
                        bg_custom_path = temp_bg_custom_path
                        bg_pattern_color = temp_bg_pattern_color
                        set_window_topmost(always_on_top)
                        init_fonts()
                        update_theme_colors()
                        save_config(username, cur_ver)
                        add_log("[System] Настройки применены.")

                    elif settings_cancel_btn.collidepoint(event.pos):
                        temp_theme = current_theme
                        temp_accent_idx = accent_idx
                        temp_custom_color = custom_color
                        temp_ram_gb = ram_gb
                        temp_ram_protection = ram_protection
                        temp_launch_action = launch_action
                        temp_auto_backup_enabled = auto_backup_enabled
                        temp_always_on_top = always_on_top
                        temp_auto_disable_incompatible_mods = auto_disable_incompatible_mods
                        temp_check_updates_on_start = check_updates_on_start
                        temp_sound_notifications = sound_notifications
                        temp_open_error_log_on_failed_launch = open_error_log_on_failed_launch
                        temp_auto_start = auto_start
                        temp_interface_scale = interface_scale
                        temp_ui_language = ui_language
                        temp_bg_mode = bg_mode
                        temp_bg_preset = bg_preset
                        temp_bg_custom_path = bg_custom_path
                        temp_bg_pattern_color = bg_pattern_color
                        color_picker_open = False
                        bg_color_picker_open = False
                        add_log("[System] Отменено.")

                    if settings_tab == "general":
                        total_sys_ram = get_total_system_ram()
                        max_lim = total_sys_ram if not temp_ram_protection else max(2, total_sys_ram - 1)

                        if language_dropdown_rect.collidepoint(event.pos):
                            language_dropdown_open = not language_dropdown_open
                        elif language_dropdown_open and lang_drop_menu_rect.collidepoint(event.pos):
                            langs = ["en", "ru", "uk"]
                            idx = max(0, min(len(langs) - 1, (event.pos[1] - lang_drop_menu_rect.y) // 34))
                            lang_code = langs[idx]
                            temp_ui_language = lang_code
                            translator.set_language(lang_code)
                            language_dropdown_open = False
                        elif language_dropdown_open and not lang_drop_menu_rect.collidepoint(event.pos):
                            language_dropdown_open = False
                        elif ram_minus_btn.collidepoint(event.pos) and temp_ram_gb > 2:
                            temp_ram_gb -= 1
                        elif ram_plus_btn.collidepoint(event.pos) and temp_ram_gb < max_lim:
                            temp_ram_gb += 1
                        elif ram_protection_toggle_btn.collidepoint(event.pos):
                            temp_ram_protection = not temp_ram_protection
                            if temp_ram_gb > (total_sys_ram if not temp_ram_protection else max(2, total_sys_ram - 1)):
                                temp_ram_gb = total_sys_ram if not temp_ram_protection else max(2, total_sys_ram - 1)
                        elif action_toggle_btn.collidepoint(event.pos):
                            actions = ["close", "hide", "none"]
                            next_idx = (actions.index(temp_launch_action) + 1) % len(actions)
                            temp_launch_action = actions[next_idx]
                        elif auto_backup_btn.collidepoint(event.pos):
                            temp_auto_backup_enabled = not temp_auto_backup_enabled
                        elif check_updates_btn.collidepoint(event.pos):
                            has_update, version = check_for_launcher_updates_now()
                            if has_update:
                                add_log(f"[Update] Обновление доступно: {version or 'archive'}")
                            else:
                                add_log("[Update] Обновления не найдены.")
                        elif topmost_toggle_btn.collidepoint(event.pos):
                            temp_always_on_top = not temp_always_on_top
                        elif incompatible_toggle_btn.collidepoint(event.pos):
                            temp_auto_disable_incompatible_mods = not temp_auto_disable_incompatible_mods
                        elif updates_start_toggle_btn.collidepoint(event.pos):
                            temp_check_updates_on_start = not temp_check_updates_on_start
                        elif sound_toggle_btn.collidepoint(event.pos):
                            temp_sound_notifications = not temp_sound_notifications
                        elif error_log_toggle_btn.collidepoint(event.pos):
                            temp_open_error_log_on_failed_launch = not temp_open_error_log_on_failed_launch
                        elif auto_start_toggle_btn.collidepoint(event.pos):
                            temp_auto_start = not temp_auto_start
                        else:
                            for scale_value, rect in scale_buttons.items():
                                if rect.collidepoint(event.pos):
                                    temp_interface_scale = float(scale_value)
                                    break

                    elif settings_tab == "appearance":
                        toggle_edit_layout_btn.y = settings_content_rect.y + 430 + (PICKER_SIZE if bg_color_picker_open else 0)
                        if theme_dark_btn.collidepoint(event.pos):
                            temp_theme = "dark"
                        elif theme_light_btn.collidepoint(event.pos):
                            temp_theme = "light"

                        elif bg_none_btn.collidepoint(event.pos):
                            temp_bg_mode = "none"

                        elif bg_custom_btn.collidepoint(event.pos):
                            path = select_custom_bg_dialog()
                            if path:
                                temp_bg_custom_path = path
                                temp_bg_mode = "custom"

                        elif toggle_edit_layout_btn.collidepoint(event.pos) and not color_picker_open and not bg_color_picker_open:
                            edit_layout_mode = not edit_layout_mode
                            current_page = "main"

                        total_color_buttons = len(DEFAULT_PRESETS) + 1
                        for idx in range(total_color_buttons):
                            color_circle_rect = pygame.Rect(settings_content_rect.x + 30 + idx * 50, settings_content_rect.y + 180, 36, 36)
                            if color_circle_rect.collidepoint(event.pos):
                                if idx == len(DEFAULT_PRESETS):
                                    color_picker_open = not color_picker_open
                                    temp_accent_idx = idx
                                else:
                                    color_picker_open = False
                                    temp_accent_idx = idx
                                break

                        for idx in range(total_color_buttons):
                            bg_c_circle = pygame.Rect(settings_content_rect.x + 30 + idx * 50, settings_content_rect.y + 360, 36, 36)
                            if bg_c_circle.collidepoint(event.pos):
                                if idx == len(DEFAULT_PRESETS):
                                    bg_color_picker_open = not bg_color_picker_open
                                else:
                                    bg_color_picker_open = False
                                    temp_bg_pattern_color = DEFAULT_PRESETS[idx]
                                break

                        bg_files = [f for f in os.listdir(BACKGROUNDS_DIR) if f.lower().endswith(".png")]
                        for p_idx, bg_f in enumerate(bg_files):
                            p_btn_rect = pygame.Rect(settings_content_rect.x + 30 + (p_idx % 5) * 85, settings_content_rect.y + 295 + (p_idx // 5) * 35, 75, 28)
                            if p_btn_rect.collidepoint(event.pos):
                                temp_bg_preset = os.path.splitext(bg_f)[0]
                                temp_bg_mode = "preset"


            if event.type == pygame.KEYDOWN:
                if current_page == "main":
                    if edit_layout_mode and event.key == pygame.K_ESCAPE:
                        edit_layout_mode = False
                    elif nickname_input_active:
                        if event.key == pygame.K_BACKSPACE:
                            nickname_input_text = nickname_input_text[:-1]
                        elif event.key == pygame.K_RETURN:
                            new_nick = nickname_input_text.strip()[:16]
                            if new_nick:
                                if new_nick not in nickname_profiles:
                                    nickname_profiles[new_nick] = cur_ver
                                    active_nickname = new_nick
                                    username = new_nick
                                    save_config(username, cur_ver)
                            nickname_input_active = False
                            nickname_input_text = ""
                        elif event.key == pygame.K_ESCAPE:
                            nickname_input_active = False
                            nickname_input_text = ""
                        elif len(nickname_input_text) < 16 and event.unicode.isprintable():
                            nickname_input_text += event.unicode
                    elif input_active:
                        if event.key == pygame.K_BACKSPACE:
                            username = username[:-1]
                        elif event.key == pygame.K_RETURN:
                            input_active = False
                            save_config(username, cur_ver)
                        elif len(username) < 16 and event.unicode.isprintable():
                            username += event.unicode
                    elif center_active_tab == "downloaded" and downloaded_mod_search_active:
                        if event.key == pygame.K_BACKSPACE:
                            downloaded_mod_search_text = downloaded_mod_search_text[:-1]
                        elif event.key == pygame.K_ESCAPE:
                            downloaded_mod_search_active = False
                        elif event.unicode.isprintable():
                            downloaded_mod_search_text += event.unicode
                    elif center_active_tab == "browser" and mod_browser_search_active:
                        if event.key == pygame.K_BACKSPACE:
                            mod_browser_search_text = mod_browser_search_text[:-1]
                        elif event.key == pygame.K_RETURN:
                            load_browser_page(reset=True)
                        elif event.unicode.isprintable():
                            mod_browser_search_text += event.unicode
                    elif center_active_tab == "resourcepacks" and rp_browser_search_active:
                        if event.key == pygame.K_BACKSPACE:
                            rp_browser_search_text = rp_browser_search_text[:-1]
                        elif event.key == pygame.K_RETURN:
                            load_rp_browser_page(reset=True)
                        elif event.unicode.isprintable():
                            rp_browser_search_text += event.unicode


                elif current_page == "mods" and downloaded_mod_search_active:
                    if event.key == pygame.K_BACKSPACE:
                        downloaded_mod_search_text = downloaded_mod_search_text[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        downloaded_mod_search_active = False
                    elif event.unicode.isprintable():
                        downloaded_mod_search_text += event.unicode
        screen.fill(BG_COLOR)

        # Фиксированная 50px боковая панель.
        pygame.draw.rect(screen, PANEL_BG, sidebar_rect)
        pygame.draw.line(screen, BORDER_COLOR, (50, 0), (50, cur_h), 1)
        sidebar_buttons = [
            (sidebar_profile_btn, "optpin", current_page == "main"),
            (sidebar_settings_btn, "settings", current_page == "settings"),
            (sidebar_files_btn, "folder", False),
            (sidebar_update_btn, "update", False),
            (sidebar_networks_btn, "networks", False),
        ]
        for s_rect, icon_key, selected in sidebar_buttons:
            pygame.draw.rect(screen, ACCENT_COLOR if selected else CARD_BG, s_rect, border_radius=8)
            icon = icons_cache.get(icon_key)
            if icon:
                screen.blit(icon, (s_rect.centerx - icon.get_width() // 2, s_rect.centery - icon.get_height() // 2))

        TOP_BAR_HEIGHT = 48
        top_bar_rect = pygame.Rect(60, 10, cur_w - 70, TOP_BAR_HEIGHT - 6)
        pygame.draw.rect(screen, PANEL_BG, top_bar_rect, border_radius=10)
        pygame.draw.rect(screen, BORDER_COLOR, top_bar_rect, width=1, border_radius=10)
        
        logo_reserved_x = top_bar_rect.x + 15
        header_title_surf = font_subtitle.render("Mace Launcher - Minecraft assembler", True, TEXT_COLOR)
        screen.blit(header_title_surf, (logo_reserved_x + 36, top_bar_rect.y + (top_bar_rect.height - header_title_surf.get_height()) // 2))
        if is_ui_busy() or mod_browser_is_loading_more:
            draw_activity_spinner(
                screen,
                (top_bar_rect.right - 22, top_bar_rect.centery),
                ticks,
                ACCENT_COLOR,
            )

        if current_page == "main":
            def get_wiggle_offset(idx):
                if not edit_layout_mode:
                    return 0, 0
                angle = math.sin((ticks + idx * 150) * 0.015) * 3
                offset_y = math.cos((ticks + idx * 120) * 0.012) * 2
                return angle, offset_y

            if edit_layout_mode:
                for r_idx, ry in enumerate(row_y_coords):
                    for c_idx, cx in enumerate(col_x_coords):
                        cell_rect = pygame.Rect(cx, ry, col_widths[c_idx], row_heights[r_idx])
                        pygame.draw.rect(screen, CARD_BG, cell_rect, border_radius=12)
                        pygame.draw.rect(screen, BORDER_COLOR, cell_rect, width=1, border_radius=12)

                for _, d_rect in grid_divider_rects_v:
                    pygame.draw.rect(screen, ACCENT_COLOR, d_rect, border_radius=4)

            openwindow_icon = icons_cache.get("openwindow")

            for mod_idx, (mod_id, r) in enumerate(module_rects.items()):
                if mod_id in detached_modules:
                    if not edit_layout_mode:
                        pygame.draw.rect(screen, PANEL_BG, r, border_radius=12)
                        pygame.draw.rect(screen, BORDER_COLOR, r, width=1, border_radius=12)
                        
                        d_btn = detach_btn_rects[mod_id]
                        btn_hover = d_btn.collidepoint(mouse_pos)
                        pygame.draw.rect(screen, ACCENT_COLOR if btn_hover else CARD_BG, d_btn, border_radius=6)
                        pygame.draw.rect(screen, BORDER_COLOR, d_btn, width=1, border_radius=6)
                        
                        if openwindow_icon:
                            screen.blit(openwindow_icon, (d_btn.centerx - openwindow_icon.get_width() // 2, d_btn.centery - openwindow_icon.get_height() // 2))
                        else:
                            screen.blit(font_small.render("↙", True, TEXT_COLOR), (d_btn.x + 8, d_btn.y + 6))

                        det_surf = font_main.render(f"{tr('module')} [{mod_id.upper()}] {tr('in_window')}", True, GRAY_TEXT)
                        screen.blit(det_surf, (r.centerx - det_surf.get_width() // 2, r.centery - 10))
                    continue

                if dragged_module == mod_id:
                    draw_x = mouse_pos[0] - drag_offset_x
                    draw_y = mouse_pos[1] - drag_offset_y
                else:
                    w_x, w_y = get_wiggle_offset(mod_idx)
                    draw_x = r.x + w_x
                    draw_y = r.y + w_y

                p_rect = pygame.Rect(draw_x, draw_y, r.width, r.height)
                pygame.draw.rect(screen, PANEL_BG, p_rect, border_radius=12)
                draw_module_background(screen, p_rect, bg_mode, bg_preset, bg_custom_path, bg_pattern_color)
                pygame.draw.rect(screen, ACCENT_COLOR if edit_layout_mode else BORDER_COLOR, p_rect, width=2 if edit_layout_mode else 1, border_radius=12)

                if not edit_layout_mode:
                    d_btn = detach_btn_rects[mod_id]
                    btn_hover = d_btn.collidepoint(mouse_pos)
                    pygame.draw.rect(screen, ACCENT_COLOR if btn_hover else CARD_BG, d_btn, border_radius=6)
                    pygame.draw.rect(screen, BORDER_COLOR, d_btn, width=1, border_radius=6)
                    
                    if openwindow_icon:
                        screen.blit(openwindow_icon, (d_btn.centerx - openwindow_icon.get_width() // 2, d_btn.centery - openwindow_icon.get_height() // 2))
                    else:
                        screen.blit(font_small.render("↗", True, TEXT_COLOR), (d_btn.x + 8, d_btn.y + 6))

                if mod_id == "left":
                    pygame.draw.rect(screen, INPUT_BG, nickname_dropdown_rect, border_radius=8)
                    pygame.draw.rect(screen, ACCENT_COLOR if nickname_build_menu_open else BORDER_COLOR, nickname_dropdown_rect, width=1, border_radius=8)
                    current_nick = active_nickname or username or "Никнейм"
                    shown = current_nick + ("|" if nickname_input_active else "")
                    screen.blit(font_main.render(shown[:18], True, TEXT_COLOR), (nickname_dropdown_rect.x + 12, nickname_dropdown_rect.centery - 7))
                    screen.blit(font_small.render("▼" if not nickname_build_menu_open else "▲", True, GRAY_TEXT), (nickname_dropdown_rect.right - 24, nickname_dropdown_rect.centery - 6))

                    if nickname_items:
                        for nick, item_rect in nickname_items:
                            # Список виден только при открытии выпадающей панели.
                            if nickname_build_menu_open and nickname_build_target != nick:
                                continue
                            if not nickname_build_menu_open and nick != active_nickname:
                                continue
                            pygame.draw.rect(screen, ACCENT_COLOR if nick == active_nickname else CARD_BG, item_rect, border_radius=7)
                            screen.blit(font_small.render(nick[:14], True, TEXT_COLOR), (item_rect.x + 10, item_rect.centery - 6))
                            build_name = nickname_profiles.get(nick, "") or "Без сборки"
                            screen.blit(font_small.render(build_name[:12], True, GRAY_TEXT), (item_rect.x + 105, item_rect.centery - 6))
                            pygame.draw.rect(screen, DANGER_COLOR, nickname_delete_btns[nick], border_radius=5)
                            screen.blit(font_small.render("×", True, TEXT_COLOR), (nickname_delete_btns[nick].centerx - 4, nickname_delete_btns[nick].centery - 6))
                            pygame.draw.rect(screen, ACCENT_COLOR, nickname_plus_btns[nick], border_radius=5)
                            screen.blit(font_small.render("+", True, TEXT_COLOR), (nickname_plus_btns[nick].centerx - 4, nickname_plus_btns[nick].centery - 6))

                    if nickname_input_active:
                        pygame.draw.rect(screen, CARD_BG, add_nickname_btn, border_radius=8)
                        screen.blit(font_small.render(nickname_input_text + "|", True, TEXT_COLOR), (add_nickname_btn.x + 10, add_nickname_btn.centery - 6))
                    else:
                        pygame.draw.rect(screen, CARD_BG, add_nickname_btn, border_radius=8)
                        pygame.draw.rect(screen, BORDER_COLOR, add_nickname_btn, width=1, border_radius=8)
                        add_s = font_small.render("+ Добавить никнейм", True, TEXT_COLOR)
                        screen.blit(add_s, (add_nickname_btn.centerx - add_s.get_width() // 2, add_nickname_btn.centery - 6))

                    if nickname_build_menu_open and nickname_build_target:
                        pygame.draw.rect(screen, PANEL_BG, nickname_build_menu_rect, border_radius=8)
                        pygame.draw.rect(screen, BORDER_COLOR, nickname_build_menu_rect, width=1, border_radius=8)
                        old_clip = screen.get_clip()
                        screen.set_clip(nickname_build_menu_rect)
                        for vi, vv in enumerate(versions):
                            br = pygame.Rect(nickname_build_menu_rect.x + 4, nickname_build_menu_rect.y + 4 + vi * 34, nickname_build_menu_rect.width - 8, 30)
                            pygame.draw.rect(screen, ACCENT_COLOR if nickname_profiles.get(nickname_build_target) == vv else CARD_BG, br, border_radius=5)
                            screen.blit(font_small.render(vv[:22], True, TEXT_COLOR), (br.x + 8, br.centery - 6))
                        screen.set_clip(old_clip)

                elif mod_id == "info":
                    draw_info_module_content(screen, p_rect, cur_fps, running_state)

                elif mod_id == "console":
                    screen.blit(font_small.render(tr("system_console"), True, GRAY_TEXT), (p_rect.x + 15, p_rect.y + 12))

                    console_box = pygame.Rect(p_rect.x + 12, p_rect.y + 35, p_rect.width - 24, p_rect.height - 47)
                    console_log_lines = get_live_logs()
                    max_visible_lines = max(2, (console_box.height - 40) // 18)
                    max_scroll = max(0, len(console_log_lines) - max_visible_lines)
                    console_scroll_offset = max(0, min(console_scroll_offset, max_scroll))

                    copy_btn = pygame.Rect(console_box.right - 96, console_box.y + 8, 84, 22)
                    pygame.draw.rect(screen, INPUT_BG, console_box, border_radius=8)
                    pygame.draw.rect(screen, BORDER_COLOR, console_box, width=1, border_radius=8)
                    pygame.draw.rect(screen, CARD_BG, copy_btn, border_radius=6)
                    pygame.draw.rect(screen, BORDER_COLOR, copy_btn, width=1, border_radius=6)
                    screen.blit(font_small.render(tr("copy"), True, TEXT_COLOR), (copy_btn.x + 8, copy_btn.y + 5))

                    log_start = console_scroll_offset
                    visible_logs = console_log_lines[log_start:log_start + max_visible_lines]
                    y_offset = console_box.y + 10
                    for line in visible_logs:
                        line_text = str(line)
                        max_chars = max(10, (console_box.width - 46) // 7)
                        if len(line_text) > max_chars:
                            line_text = line_text[:max_chars - 3] + "..."
                        log_surf = font_console.render(line_text, True, CONSOLE_TEXT if "Ошибка" not in line_text.lower() and "не" not in line_text.lower() else (255, 180, 180))
                        screen.blit(log_surf, (console_box.x + 8, y_offset))
                        y_offset += 18

                    scroll_track = pygame.Rect(console_box.right - 14, console_box.y + 8, 6, console_box.height - 16)
                    pygame.draw.rect(screen, INPUT_BG, scroll_track, border_radius=4)
                    if max_scroll > 0:
                        thumb_h = max(18, int((max_visible_lines / max(1, len(console_log_lines))) * max(1, scroll_track.height)))
                        thumb_y = scroll_track.y + int((console_scroll_offset / max_scroll) * max(1, scroll_track.height - thumb_h))
                        pygame.draw.rect(screen, ACCENT_COLOR, pygame.Rect(scroll_track.x, thumb_y, scroll_track.width, thumb_h), border_radius=4)

                elif mod_id == "center":
                    screen.blit(font_small.render(f"{tr('news_tab')} / {tr('mods_tab')} / {tr('resourcepacks_tab')}", True, GRAY_TEXT), (p_rect.x + 15, p_rect.y + 12))
                     
                    # Отрисовка вкладок внутри центрального модуля
                    tab_y = p_rect.y + 35
                    tab_gap = 5
                    tab_w = max(64, int((p_rect.width - 30 - tab_gap * 3) / 4))
                    tab_news_rect = pygame.Rect(p_rect.x + 15, tab_y, tab_w, 30)
                    tab_downloaded_rect = pygame.Rect(tab_news_rect.right + tab_gap, tab_y, tab_w, 30)
                    tab_browser_rect = pygame.Rect(tab_downloaded_rect.right + tab_gap, tab_y, tab_w, 30)
                    tab_rp_rect = pygame.Rect(tab_browser_rect.right + tab_gap, tab_y, tab_w, 30)

                    def draw_tab_btn(rect, title, is_active):
                        pygame.draw.rect(screen, ACCENT_COLOR if is_active else CARD_BG, rect, border_radius=6)
                        pygame.draw.rect(screen, BORDER_COLOR, rect, width=1, border_radius=6)
                        t_surf = font_small.render(title, True, TEXT_COLOR)
                        screen.blit(t_surf, (rect.centerx - t_surf.get_width()//2, rect.centery - t_surf.get_height()//2))

                    draw_tab_btn(tab_news_rect, tr("news_tab"), center_active_tab == "news")
                    draw_tab_btn(tab_downloaded_rect, tr("downloaded_tab"), center_active_tab == "downloaded")
                    draw_tab_btn(tab_browser_rect, tr("mods_tab"), center_active_tab == "browser")
                    draw_tab_btn(tab_rp_rect, tr("resourcepacks_tab"), center_active_tab == "resourcepacks")

                    center_box = pygame.Rect(p_rect.x + 12, p_rect.y + 75, p_rect.width - 24, p_rect.height - 87)
                    pygame.draw.rect(screen, INPUT_BG, center_box, border_radius=8)
                    pygame.draw.rect(screen, BORDER_COLOR, center_box, width=1, border_radius=8)

                    if center_active_tab == "news":


                        # Главная вкладка без Music Player.


                        pass

                    elif center_active_tab == "downloaded":
                        search_box_rect = pygame.Rect(center_box.x + 10, center_box.y + 10, center_box.width - 120, 36)
                        folder_btn_rect = pygame.Rect(search_box_rect.right + 10, center_box.y + 10, 95, 36)
                        pygame.draw.rect(screen, CARD_BG, search_box_rect, border_radius=6)
                        pygame.draw.rect(screen, ACCENT_COLOR if downloaded_mod_search_active else BORDER_COLOR, search_box_rect, width=2 if downloaded_mod_search_active else 1, border_radius=6)
                        search_display = downloaded_mod_search_text + ("|" if downloaded_mod_search_active else "")
                        if not search_display:
                            search_display = tr("search_mods")
                        screen.blit(font_main.render(search_display, True, TEXT_COLOR if downloaded_mod_search_text else GRAY_TEXT), (search_box_rect.x + 10, search_box_rect.y + 10))
                        pygame.draw.rect(screen, CARD_BG, folder_btn_rect, border_radius=6)
                        pygame.draw.rect(screen, BORDER_COLOR, folder_btn_rect, width=1, border_radius=6)
                        folder_icon = icons_cache.get("folder")
                        if folder_icon:
                            screen.blit(folder_icon, (folder_btn_rect.centerx - folder_icon.get_width() // 2, folder_btn_rect.centery - folder_icon.get_height() // 2))
                        filtered_mods = [m for m in local_mods if not downloaded_mod_search_text.strip() or downloaded_mod_search_text.lower() in m.lower()]
                        downloaded_clip = pygame.Rect(center_box.x + 10, center_box.y + 55, center_box.width - 20, center_box.height - 65)
                        max_downloaded_scroll = max(0, len(filtered_mods) * 55 - downloaded_clip.height + 10)
                        downloaded_mod_scroll_offset = max(0, min(downloaded_mod_scroll_offset, max_downloaded_scroll))
                        old_clip = screen.get_clip()
                        screen.set_clip(downloaded_clip)
                        if not filtered_mods:
                            msg = tr("no_downloaded_mods") if not downloaded_mod_search_text.strip() else tr("not_detected")
                            lbl = font_main.render(msg, True, GRAY_TEXT)
                            screen.blit(lbl, (downloaded_clip.centerx - lbl.get_width() // 2, downloaded_clip.centery - 10))
                        else:
                            for idx, mod_file in enumerate(filtered_mods):
                                item_y = downloaded_clip.y + 5 + idx * 55 - downloaded_mod_scroll_offset
                                item_r = pygame.Rect(downloaded_clip.x, item_y, downloaded_clip.width - 8, 48)
                                if item_r.bottom < downloaded_clip.y or item_r.y > downloaded_clip.bottom:
                                    continue
                                pygame.draw.rect(screen, CARD_BG, item_r, border_radius=8)
                                pygame.draw.rect(screen, BORDER_COLOR, item_r, width=1, border_radius=8)
                                icon = get_mod_icon_surface({"icon_url": ""}, size=(30, 30))
                                screen.blit(icon, (item_r.x + 8, item_r.centery - 15))
                                screen.blit(font_small.render(mod_file[:42], True, TEXT_COLOR), (item_r.x + 48, item_r.centery - 7))
                                is_disabled = mod_file.endswith(".disabled")
                                toggle_r = pygame.Rect(item_r.right - 170, item_r.y + 9, 76, 30)
                                del_r = pygame.Rect(item_r.right - 86, item_r.y + 9, 76, 30)
                                pygame.draw.rect(screen, SUCCESS_COLOR if is_disabled else (200, 140, 40), toggle_r, border_radius=6)
                                pygame.draw.rect(screen, DANGER_COLOR, del_r, border_radius=6)
                                screen.blit(font_small.render(tr("on") if is_disabled else tr("off"), True, TEXT_COLOR), (toggle_r.centerx - 12, toggle_r.centery - 6))
                                screen.blit(font_small.render(tr("delete"), True, TEXT_COLOR), (del_r.centerx - 20, del_r.centery - 6))
                        screen.set_clip(old_clip)
                    elif center_active_tab in ("browser", "resourcepacks"):
                        is_rp = center_active_tab == "resourcepacks"
                        if is_rp and last_rp_browser_search_query is None and not rp_browser_is_loading_more:
                            load_rp_browser_page(reset=True)
                        elif not is_rp and last_browser_search_query is None and not mod_browser_is_loading_more:
                            load_browser_page(reset=True)

                        search_box_rect = pygame.Rect(center_box.x + 10, center_box.y + 10, center_box.width - 125, 36)
                        action_btn_rect = pygame.Rect(search_box_rect.right + 10, center_box.y + 10, 95, 36)
                        results_clip_rect = pygame.Rect(center_box.x + 10, center_box.y + 55, max(200, center_box.width - 60), center_box.height - 65)
                        browser_scroll_track = pygame.Rect(results_clip_rect.right + 6, results_clip_rect.y + 12, 14, max(40, results_clip_rect.height - 24))

                        result_items = cached_rp_results if is_rp else cached_mod_results
                        current_scroll = rp_browser_scroll_offset if is_rp else mod_browser_scroll_offset
                        pack_info = get_modpack_compatibility(cur_ver)
                        target_mc = pack_info.get("minecraft_version", "")
                        placeholder = tr("enter_resourcepack_name") if is_rp else tr("enter_mod_name")
                        action_title = tr("search") if is_rp else tr("filter")
                        max_b_scroll = max(0, len(result_items) * 65 - results_clip_rect.height)
                        thumb_h = max(28, int(browser_scroll_track.height * (results_clip_rect.height / max(1, len(result_items) * 65)))) if result_items else browser_scroll_track.height
                        thumb_h = min(browser_scroll_track.height, thumb_h)
                        browser_scroll_thumb = pygame.Rect(
                            browser_scroll_track.x - 2,
                            browser_scroll_track.y + int((current_scroll / max_b_scroll) * max(1, browser_scroll_track.height - thumb_h)) if max_b_scroll > 0 else browser_scroll_track.y,
                            browser_scroll_track.width + 4,
                            thumb_h,
                        )

                        active_search = rp_browser_search_active if is_rp else mod_browser_search_active
                        search_text = rp_browser_search_text if is_rp else mod_browser_search_text
                        pygame.draw.rect(screen, CARD_BG, search_box_rect, border_radius=6)
                        pygame.draw.rect(screen, ACCENT_COLOR if active_search else BORDER_COLOR, search_box_rect, width=2 if active_search else 1, border_radius=6)
                        display_search_txt = search_text + ("|" if active_search else "")
                        if not display_search_txt:
                            display_search_txt = placeholder
                        screen.blit(font_main.render(display_search_txt, True, TEXT_COLOR if search_text else GRAY_TEXT), (search_box_rect.x + 10, search_box_rect.y + 10))

                        pygame.draw.rect(screen, ACCENT_COLOR, action_btn_rect, border_radius=6)
                        action_surf = font_small.render(action_title, True, TEXT_COLOR)
                        screen.blit(action_surf, (action_btn_rect.centerx - action_surf.get_width() // 2, action_btn_rect.centery - action_surf.get_height() // 2))

                        info_text = f"{tr('selected_modpack')}: {cur_ver or tr('not_selected')} | {tr('minecraft')}: {target_mc or tr('not_detected')}"
                        info_surf = font_small.render(info_text, True, SUCCESS_COLOR if target_mc else DANGER_COLOR)
                        screen.blit(info_surf, (center_box.x + 12, center_box.y + 50))

                        old_clip = screen.get_clip()
                        screen.set_clip(results_clip_rect)
                        y_off = results_clip_rect.y + 5 - current_scroll
                        if not result_items:
                            empty_text = "Выберите мод-пак" if is_rp and not cur_ver else (f"Нет ресурс-паков для {target_mc}" if is_rp and target_mc else "Введите запрос или нажмите Фильтры")
                            empty_lbl = font_main.render(empty_text, True, GRAY_TEXT)
                            screen.blit(empty_lbl, (results_clip_rect.centerx - empty_lbl.get_width()//2, results_clip_rect.centery - 10))
                        else:
                            visible_start = int(current_scroll // 65)
                            visible_end = min(len(result_items), visible_start + max(1, (results_clip_rect.height // 65) + 4))
                            for idx in range(visible_start, visible_end):
                                item = result_items[idx]
                                item_r = pygame.Rect(results_clip_rect.x, y_off + idx * 65, results_clip_rect.width - 18, 55)
                                pygame.draw.rect(screen, PANEL_BG, item_r, border_radius=6)
                                pygame.draw.rect(screen, BORDER_COLOR, item_r, width=1, border_radius=6)
                                icon = get_mod_icon_surface(item, size=(34, 34))
                                screen.blit(icon, (item_r.x + 10, item_r.y + 10))
                                title = item.get("name") if is_rp else item.get("title")
                                title = title or ("Resource Pack" if is_rp else "Mod")
                                desc = item.get("description") or "Без описания"
                                screen.blit(font_main.render(str(title)[:30], True, TEXT_COLOR), (item_r.x + 54, item_r.y + 7))
                                desc_text = str(desc)
                                screen.blit(font_small.render(desc_text[:40] + ("..." if len(desc_text) > 40 else ""), True, GRAY_TEXT), (item_r.x + 54, item_r.y + 28))

                                if is_rp:
                                    project_id = item.get("id") or item.get("project_id")
                                    installed = bool(project_id and cur_ver and is_resource_pack_installed(project_id, get_target_resourcepacks_dir(cur_ver), target_mc))
                                else:
                                    slug = item.get("slug")
                                    installed = bool(slug and is_mod_installed_by_slug(slug, mods_dir_path))

                                install_btn = pygame.Rect(item_r.right - 78, item_r.y + 12, 68, 30)
                                if installed:
                                    pygame.draw.rect(screen, CARD_BG, install_btn, border_radius=6)
                                    pygame.draw.rect(screen, BORDER_COLOR, install_btn, width=1, border_radius=6)
                                    label = "Установлен"
                                else:
                                    pygame.draw.rect(screen, SUCCESS_COLOR, install_btn, border_radius=6)
                                    label = "Установить"
                                label_surf = font_small.render(label, True, TEXT_COLOR if not installed else GRAY_TEXT)
                                screen.blit(label_surf, (install_btn.centerx - label_surf.get_width() // 2, install_btn.centery - label_surf.get_height() // 2))
                        screen.set_clip(old_clip)

                        browser_scroll_up_btn = pygame.Rect(browser_scroll_track.x - 2, browser_scroll_track.y - 18, browser_scroll_track.width + 4, 16)
                        browser_scroll_down_btn = pygame.Rect(browser_scroll_track.x - 2, browser_scroll_track.bottom + 2, browser_scroll_track.width + 4, 16)
                        pygame.draw.rect(screen, (36, 36, 44), browser_scroll_up_btn, border_radius=5)
                        pygame.draw.rect(screen, (36, 36, 44), browser_scroll_down_btn, border_radius=5)
                        pygame.draw.polygon(screen, ACCENT_COLOR, [(browser_scroll_up_btn.centerx, browser_scroll_up_btn.y + 3), (browser_scroll_up_btn.x + 5, browser_scroll_up_btn.bottom - 3), (browser_scroll_up_btn.right - 5, browser_scroll_up_btn.bottom - 3)])
                        pygame.draw.polygon(screen, ACCENT_COLOR, [(browser_scroll_down_btn.centerx, browser_scroll_down_btn.bottom - 3), (browser_scroll_down_btn.x + 5, browser_scroll_down_btn.y + 3), (browser_scroll_down_btn.right - 5, browser_scroll_down_btn.y + 3)])
                        pygame.draw.rect(screen, (28, 28, 36), browser_scroll_track, border_radius=7)
                        pygame.draw.rect(screen, ACCENT_COLOR, browser_scroll_thumb, border_radius=7)

                elif mod_id == "right":
                    screen.blit(font_small.render("3D " + tr("profile").upper(), True, GRAY_TEXT), (p_rect.x + 15, p_rect.y + 12))

                    pygame.draw.rect(screen, INPUT_BG, skin_preview_box, border_radius=10)
                    pygame.draw.rect(screen, BORDER_COLOR, skin_preview_box, width=1, border_radius=10)

                    if skin_preview_box.height > 60:
                        skin_3d = render_full_3d_skin(skin_preview_box)
                        screen.blit(skin_3d, (skin_preview_box.x, skin_preview_box.y))

                    skin_status_text = tr("default_skin") if not skin_path else os.path.basename(skin_path)
                    if len(skin_status_text) > 18:
                        skin_status_text = skin_status_text[:15] + "..."
                    status_surf = font_small.render(skin_status_text, True, TEXT_COLOR)
                    screen.blit(status_surf, (skin_preview_box.centerx - status_surf.get_width() // 2, skin_preview_box.bottom - 20))

                    btn_c = ACCENT_HOVER if change_skin_btn.collidepoint(mouse_pos) else ACCENT_COLOR
                    pygame.draw.rect(screen, btn_c, change_skin_btn, border_radius=8)
                    pygame.draw.rect(screen, BORDER_COLOR, change_skin_btn, width=1, border_radius=8)
                    cs_surf = font_main.render(tr("load_skin"), True, TEXT_COLOR)
                    screen.blit(cs_surf, (change_skin_btn.centerx - cs_surf.get_width() // 2, change_skin_btn.centery - cs_surf.get_height() // 2))

                    pygame.draw.rect(screen, CARD_BG, reset_skin_btn, border_radius=8)
                    pygame.draw.rect(screen, BORDER_COLOR, reset_skin_btn, width=1, border_radius=8)
                    rs_surf = font_small.render(tr("clear_skin"), True, GRAY_TEXT)
                    screen.blit(rs_surf, (reset_skin_btn.centerx - rs_surf.get_width() // 2, reset_skin_btn.centery - rs_surf.get_height() // 2))

                if edit_layout_mode:
                    hr = resize_handle_rects[mod_id]
                    pygame.draw.rect(screen, ACCENT_COLOR, hr, border_radius=4)
                    pygame.draw.rect(screen, TEXT_COLOR, hr, width=1, border_radius=4)

            if edit_layout_mode:
                banner_rect = pygame.Rect(cur_w // 2 - 290, 20, 580, 40)
                pygame.draw.rect(screen, ACCENT_COLOR, banner_rect, border_radius=20)
                pygame.draw.rect(screen, TEXT_COLOR, banner_rect, width=2, border_radius=20)
                banner_text = font_main.render(tr("drag_grid_hint"), True, TEXT_COLOR)
                screen.blit(banner_text, (banner_rect.centerx - banner_text.get_width() // 2, banner_rect.centery - banner_text.get_height() // 2))

            pygame.draw.rect(screen, INPUT_BG, dropdown_rect, border_radius=10)
            pygame.draw.rect(screen, BORDER_COLOR, dropdown_rect, width=1, border_radius=10)

            cur_ver_text = cur_ver if cur_ver else tr("no_versions")
            ver_surf = font_main.render(cur_ver_text, True, TEXT_COLOR)
            screen.blit(ver_surf, (dropdown_rect.x + 15, dropdown_rect.centery - ver_surf.get_height() // 2))

            arrow_str = "▲" if dropdown_open else "▼"
            screen.blit(font_small.render(arrow_str, True, GRAY_TEXT), (dropdown_rect.right - 25, dropdown_rect.centery - 6))

            def draw_icon_btn(rect, icon_key, tooltip=""):
                pygame.draw.rect(screen, CARD_BG, rect, border_radius=8)
                pygame.draw.rect(screen, BORDER_COLOR, rect, width=1, border_radius=8)
                icon = icons_cache.get(icon_key)
                if icon:
                    screen.blit(icon, (rect.centerx - icon.get_width()//2, rect.centery - icon.get_height()//2))
                else:
                    screen.blit(font_small.render("?", True, TEXT_COLOR), (rect.centerx - 4, rect.centery - 6))

            draw_icon_btn(root_minecraft_folder_btn, "folder")
            draw_icon_btn(modpack_folder_btn, "folder")
            draw_icon_btn(create_version_btn, "optpin")
            draw_icon_btn(edit_version_btn, "editpin") 

            btn_color = DANGER_COLOR if running_state else SUCCESS_COLOR
            if launch_btn_rect.collidepoint(mouse_pos):
                btn_color = DANGER_HOVER if running_state else (50, 180, 80)
            pygame.draw.rect(screen, btn_color, launch_btn_rect, border_radius=10)

            launch_text = tr("stop") if running_state else tr("play_game")
            l_surf = font_title.render(launch_text.upper() if not running_state else tr("stop").upper(), True, TEXT_COLOR)
            screen.blit(l_surf, (launch_btn_rect.centerx - l_surf.get_width() // 2, launch_btn_rect.centery - l_surf.get_height() // 2))

            if dropdown_open:
                menu_height = min(220, len(versions) * 45)
                dropdown_list_rect = pygame.Rect(dropdown_rect.x, dropdown_rect.y - menu_height - 5, dropdown_rect.width, menu_height)
                pygame.draw.rect(screen, PANEL_BG, dropdown_list_rect, border_radius=8)
                pygame.draw.rect(screen, BORDER_COLOR, dropdown_list_rect, width=1, border_radius=8)

                old_clip = screen.get_clip()
                screen.set_clip(dropdown_list_rect)

                first_visible = max(0, int(versions_scroll_offset // 45))
                last_visible = min(len(versions), first_visible + (menu_height // 45) + 3)
                for i in range(first_visible, last_visible):
                    v = versions[i]
                    item_y = dropdown_list_rect.y + 5 + i * 45 - versions_scroll_offset
                    if item_y + 45 > dropdown_list_rect.y and item_y < dropdown_list_rect.bottom:
                        is_sel = (i == selected_ver_idx)
                        item_r = pygame.Rect(dropdown_list_rect.x + 5, item_y, dropdown_list_rect.width - 15, 40)
                        if is_sel:
                            pygame.draw.rect(screen, ACCENT_COLOR, item_r, border_radius=6)
                        elif item_r.collidepoint(mouse_pos):
                            pygame.draw.rect(screen, CARD_BG, item_r, border_radius=6)

                        if is_version_favorite(v):
                            pygame.draw.rect(screen, (255, 215, 45), item_r, width=2, border_radius=6)

                        screen.blit(font_main.render(v, True, TEXT_COLOR), (item_r.x + 10, item_r.centery - 7))
                        fav_btn = pygame.Rect(item_r.right - 34, item_r.y + 7, 28, 26)
                        pygame.draw.rect(screen, (255, 215, 45) if is_version_favorite(v) else BORDER_COLOR, fav_btn, border_radius=5)
                        star_icon = load_star_icon(is_version_favorite(v), (18, 18))
                        if star_icon:
                            screen.blit(star_icon, (fav_btn.centerx - star_icon.get_width() // 2, fav_btn.centery - star_icon.get_height() // 2))
                        else:
                            star = "★" if is_version_favorite(v) else "☆"
                            screen.blit(font_small.render(star, True, (255, 215, 45) if is_version_favorite(v) else TEXT_COLOR), (fav_btn.centerx - 6, fav_btn.centery - 7))

                screen.set_clip(old_clip)

                if len(versions) * 45 > menu_height:
                    scroll_bar_height = max(20, menu_height * (menu_height / (len(versions) * 45)))
                    max_scroll = max(1, len(versions) * 45 - menu_height)
                    scroll_y = dropdown_list_rect.y + 5 + (versions_scroll_offset / max_scroll) * (menu_height - 10 - scroll_bar_height)
                    scroll_bar_rect = pygame.Rect(dropdown_list_rect.right - 10, scroll_y, 6, scroll_bar_height)
                    pygame.draw.rect(screen, ACCENT_COLOR, scroll_bar_rect, border_radius=3)

        elif current_page == "mods":
            pygame.draw.rect(screen, PANEL_BG, mods_top_panel, border_radius=12)
            pygame.draw.rect(screen, BORDER_COLOR, mods_top_panel, width=1, border_radius=12)

            pygame.draw.rect(screen, CARD_BG, mods_back_btn, border_radius=8)
            pygame.draw.rect(screen, BORDER_COLOR, mods_back_btn, width=1, border_radius=8)
            screen.blit(font_main.render(f"← {tr('back')}", True, TEXT_COLOR), (mods_back_btn.x + 18, mods_back_btn.y + 9))

            pygame.draw.rect(screen, INPUT_BG, modrinth_search_rect, border_radius=8)
            pygame.draw.rect(screen, ACCENT_COLOR if downloaded_mod_search_active else BORDER_COLOR, modrinth_search_rect, width=2 if downloaded_mod_search_active else 1, border_radius=8)
            search_text = downloaded_mod_search_text + ("|" if downloaded_mod_search_active else "")
            if not search_text:
                search_text = tr("search_mods")
            screen.blit(font_main.render(search_text, True, TEXT_COLOR if downloaded_mod_search_text else GRAY_TEXT), (modrinth_search_rect.x + 12, modrinth_search_rect.y + 11))

            pygame.draw.rect(screen, CARD_BG, modrinth_install_btn, border_radius=8)
            pygame.draw.rect(screen, BORDER_COLOR, modrinth_install_btn, width=1, border_radius=8)
            hint = font_small.render(tr("search_mods"), True, GRAY_TEXT)
            screen.blit(hint, (modrinth_install_btn.centerx - hint.get_width() // 2, modrinth_install_btn.centery - hint.get_height() // 2))

            draw_icon_btn(mods_folder_btn, "folder")
            draw_icon_btn(mods_copy_btn, "copy")

            pygame.draw.rect(screen, PANEL_BG, mods_list_rect, border_radius=12)
            pygame.draw.rect(screen, BORDER_COLOR, mods_list_rect, width=1, border_radius=12)

            filtered_local_mods = [
                m for m in local_mods
                if not downloaded_mod_search_text.strip()
                or downloaded_mod_search_text.lower() in m.lower()
            ]

            old_clip = screen.get_clip()
            screen.set_clip(mods_list_rect)
            first_visible = max(0, int(mods_scroll_offset // 55))
            last_visible = min(len(filtered_local_mods), first_visible + (mods_list_rect.height // 55) + 3)
            for idx in range(first_visible, last_visible):
                mod_file = filtered_local_mods[idx]
                y_offset = mods_list_rect.y + 10 + idx * 55 - mods_scroll_offset
                item_rect = pygame.Rect(mods_list_rect.x + 10, y_offset, mods_list_rect.width - 30, 48)
                if item_rect.bottom > mods_list_rect.y and item_rect.y < mods_list_rect.bottom:
                    pygame.draw.rect(screen, CARD_BG, item_rect, border_radius=8)
                    pygame.draw.rect(screen, BORDER_COLOR, item_rect, width=1, border_radius=8)
                    icon = get_mod_icon_surface({"icon_url": ""}, size=(30, 30))
                    screen.blit(icon, (item_rect.x + 12, item_rect.centery - 15))
                    screen.blit(font_main.render(mod_file, True, TEXT_COLOR), (item_rect.x + 52, item_rect.centery - 7))

                    del_btn = pygame.Rect(item_rect.right - 90, item_rect.y + 9, 80, 30)
                    toggle_btn = pygame.Rect(del_btn.x - 90, item_rect.y + 9, 80, 30)
                    is_disabled = mod_file.endswith(".disabled")
                    toggle_text = "Включить" if is_disabled else "Отключить"
                    toggle_color = SUCCESS_COLOR if is_disabled else (200, 140, 40)
                    pygame.draw.rect(screen, toggle_color, toggle_btn, border_radius=6)
                    screen.blit(font_small.render(toggle_text, True, TEXT_COLOR), (toggle_btn.centerx - 26, toggle_btn.centery - 6))
                    pygame.draw.rect(screen, DANGER_COLOR, del_btn, border_radius=6)
                    screen.blit(font_small.render(tr("delete"), True, TEXT_COLOR), (del_btn.centerx - 22, del_btn.centery - 6))

            if not filtered_local_mods:
                empty_text = tr("no_downloaded_mods") if not downloaded_mod_search_text.strip() else tr("not_detected")
                empty_surf = font_main.render(empty_text, True, GRAY_TEXT)
                screen.blit(empty_surf, (mods_list_rect.centerx - empty_surf.get_width() // 2, mods_list_rect.centery - empty_surf.get_height() // 2))

            screen.set_clip(old_clip)
            max_mod_scroll = max(0, len(filtered_local_mods) * 55 - (mods_list_rect.height - 20))
            mods_scroll_offset = max(0, min(mods_scroll_offset, max_mod_scroll))
            if max_mod_scroll > 0:
                scroll_bar_height = max(20, mods_list_rect.height * (mods_list_rect.height / (len(filtered_local_mods) * 55)))
                scroll_y = mods_list_rect.y + 5 + (mods_scroll_offset / max_mod_scroll) * (mods_list_rect.height - 10 - scroll_bar_height)
                mods_scrollbar_rect = pygame.Rect(mods_list_rect.right - 10, scroll_y, 6, scroll_bar_height)
                pygame.draw.rect(screen, ACCENT_COLOR, mods_scrollbar_rect, border_radius=3)
        elif current_page == "settings":
            pygame.draw.rect(screen, PANEL_BG, settings_sidebar_rect, border_radius=12)
            pygame.draw.rect(screen, BORDER_COLOR, settings_sidebar_rect, width=1, border_radius=12)

            pygame.draw.rect(screen, CARD_BG, settings_back_btn, border_radius=8)
            pygame.draw.rect(screen, BORDER_COLOR, settings_back_btn, width=1, border_radius=8)
            screen.blit(font_main.render(f"← {tr('back')}", True, TEXT_COLOR), (settings_back_btn.x + 18, settings_back_btn.y + 9))

            def draw_set_tab_btn(rect, title, is_active):
                pygame.draw.rect(screen, ACCENT_COLOR if is_active else CARD_BG, rect, border_radius=8)
                pygame.draw.rect(screen, BORDER_COLOR, rect, width=1, border_radius=8)
                screen.blit(font_main.render(title, True, TEXT_COLOR), (rect.x + 15, rect.centery - 7))

            draw_set_tab_btn(set_tab_general_btn, tr("general"), settings_tab == "general")
            draw_set_tab_btn(set_tab_appearance_btn, tr("appearance"), settings_tab == "appearance")

            pygame.draw.rect(screen, PANEL_BG, settings_content_rect, border_radius=12)
            pygame.draw.rect(screen, BORDER_COLOR, settings_content_rect, width=1, border_radius=12)

            pygame.draw.rect(screen, ACCENT_COLOR, settings_apply_btn, border_radius=8)
            screen.blit(font_main.render(tr("apply"), True, TEXT_COLOR), (settings_apply_btn.centerx - 38, settings_apply_btn.centery - 7))

            pygame.draw.rect(screen, CARD_BG, settings_cancel_btn, border_radius=8)
            screen.blit(font_main.render(tr("cancel"), True, TEXT_COLOR), (settings_cancel_btn.centerx - 26, settings_cancel_btn.centery - 7))

            if settings_tab == "general":
                language_dropdown_open = locals().get("language_dropdown_open", False)
                screen.blit(font_subtitle.render(tr("ram_allocation"), True, TEXT_COLOR), (settings_general_right_x, settings_content_rect.y + 20))

                total_sys_ram = get_total_system_ram()
                max_lim = total_sys_ram if not temp_ram_protection else max(2, total_sys_ram - 1)

                pygame.draw.rect(screen, CARD_BG, ram_minus_btn, border_radius=8)
                screen.blit(font_title.render("-", True, TEXT_COLOR), (ram_minus_btn.centerx - 5, ram_minus_btn.centery - 11))

                ram_val_surf = font_clock.render(f"{temp_ram_gb} GB", True, ACCENT_COLOR)
                screen.blit(ram_val_surf, (ram_minus_btn.right + 25, ram_minus_btn.centery - 12))

                pygame.draw.rect(screen, CARD_BG, ram_plus_btn, border_radius=8)
                screen.blit(font_title.render("+", True, TEXT_COLOR), (ram_plus_btn.centerx - 7, ram_plus_btn.centery - 11))

                pygame.draw.rect(screen, ACCENT_COLOR if temp_ram_protection else CARD_BG, ram_protection_toggle_btn, border_radius=8)
                prot_txt = "Защита RAM: ВКЛ" if temp_ram_protection else "Защита RAM: ВЫКЛ"
                screen.blit(font_main.render(prot_txt, True, TEXT_COLOR), (ram_protection_toggle_btn.x + 15, ram_protection_toggle_btn.centery - 7))

                screen.blit(font_subtitle.render(tr("launch_action"), True, TEXT_COLOR), (settings_general_right_x, settings_content_rect.y + 200))
                pygame.draw.rect(screen, CARD_BG, action_toggle_btn, border_radius=8)
                act_label = LAUNCH_ACTION_LABELS.get(temp_launch_action, "Закрывать лаунчер")
                screen.blit(font_main.render(f"{tr('launch_action')}: {act_label}", True, TEXT_COLOR), (action_toggle_btn.x + 15, action_toggle_btn.centery - 7))

                screen.blit(font_subtitle.render(tr("auto_backup"), True, TEXT_COLOR), (settings_general_right_x, settings_content_rect.y + 275))
                pygame.draw.rect(screen, ACCENT_COLOR if temp_auto_backup_enabled else CARD_BG, auto_backup_btn, border_radius=8)
                backup_label = "ВКЛ" if temp_auto_backup_enabled else "ВЫКЛ"
                screen.blit(font_main.render(f"{tr('auto_backup')}: {backup_label}", True, TEXT_COLOR), (auto_backup_btn.x + 15, auto_backup_btn.centery - 7))

                screen.blit(font_subtitle.render(tr("language"), True, TEXT_COLOR), (settings_general_right_x, settings_content_rect.y + 340))
                label_map = {"en": "EN", "ru": "RU", "uk": "UK"}
                selected_label = label_map.get(temp_ui_language, "EN")
                pygame.draw.rect(screen, ACCENT_COLOR if language_dropdown_open else CARD_BG, language_dropdown_rect, border_radius=8)
                pygame.draw.rect(screen, BORDER_COLOR, language_dropdown_rect, width=1, border_radius=8)
                screen.blit(font_main.render(selected_label, True, TEXT_COLOR), (language_dropdown_rect.x + 16, language_dropdown_rect.centery - 7))
                screen.blit(font_main.render("▼", True, TEXT_COLOR), (language_dropdown_rect.right - 22, language_dropdown_rect.centery - 7))
                if language_dropdown_open:
                    pygame.draw.rect(screen, PANEL_BG, lang_drop_menu_rect, border_radius=8)
                    pygame.draw.rect(screen, BORDER_COLOR, lang_drop_menu_rect, width=1, border_radius=8)
                    for idx, lang_code in enumerate(["en", "ru", "uk"]):
                        item_rect = pygame.Rect(lang_drop_menu_rect.x + 4, lang_drop_menu_rect.y + 4 + idx * 32, lang_drop_menu_rect.width - 8, 28)
                        is_selected = temp_ui_language == lang_code
                        pygame.draw.rect(screen, ACCENT_COLOR if is_selected else CARD_BG, item_rect, border_radius=6)
                        screen.blit(font_main.render(label_map[lang_code], True, TEXT_COLOR), (item_rect.x + 12, item_rect.centery - 7))

                screen.blit(font_subtitle.render(tr("interface_scale"), True, TEXT_COLOR), (settings_general_left_x, settings_content_rect.y + 20))
                for scale_value, rect in scale_buttons.items():
                    is_selected = abs(temp_interface_scale - float(scale_value)) < 1e-6
                    pygame.draw.rect(screen, ACCENT_COLOR if is_selected else CARD_BG, rect, border_radius=8)
                    pygame.draw.rect(screen, BORDER_COLOR, rect, width=1, border_radius=8)
                    screen.blit(font_main.render(f"{int(scale_value * 100)}%", True, TEXT_COLOR), (rect.centerx - 17, rect.centery - 7))

                pygame.draw.rect(screen, ACCENT_COLOR if temp_always_on_top else CARD_BG, topmost_toggle_btn, border_radius=8)
                screen.blit(font_main.render(f"{tr('always_on_top')}: {tr('on' if temp_always_on_top else 'off')}", True, TEXT_COLOR), (topmost_toggle_btn.x + 15, topmost_toggle_btn.centery - 7))

                pygame.draw.rect(screen, ACCENT_COLOR if temp_auto_disable_incompatible_mods else CARD_BG, incompatible_toggle_btn, border_radius=8)
                screen.blit(font_main.render(f"{tr('auto_disable_incompatible_mods')}: {tr('on' if temp_auto_disable_incompatible_mods else 'off')}", True, TEXT_COLOR), (incompatible_toggle_btn.x + 15, incompatible_toggle_btn.centery - 7))

                pygame.draw.rect(screen, ACCENT_COLOR if temp_check_updates_on_start else CARD_BG, updates_start_toggle_btn, border_radius=8)
                screen.blit(font_main.render(f"{tr('check_updates_on_start')}: {tr('on' if temp_check_updates_on_start else 'off')}", True, TEXT_COLOR), (updates_start_toggle_btn.x + 15, updates_start_toggle_btn.centery - 7))

                pygame.draw.rect(screen, ACCENT_COLOR if temp_sound_notifications else CARD_BG, sound_toggle_btn, border_radius=8)
                screen.blit(font_main.render(f"{tr('sound_notifications')}: {tr('on' if temp_sound_notifications else 'off')}", True, TEXT_COLOR), (sound_toggle_btn.x + 15, sound_toggle_btn.centery - 7))

                pygame.draw.rect(screen, ACCENT_COLOR if temp_open_error_log_on_failed_launch else CARD_BG, error_log_toggle_btn, border_radius=8)
                screen.blit(font_main.render(f"{tr('open_error_log_on_failed_launch')}: {tr('on' if temp_open_error_log_on_failed_launch else 'off')}", True, TEXT_COLOR), (error_log_toggle_btn.x + 15, error_log_toggle_btn.centery - 7))

                pygame.draw.rect(screen, ACCENT_COLOR if temp_auto_start else CARD_BG, auto_start_toggle_btn, border_radius=8)
                screen.blit(font_main.render(f"{tr('auto_start')}: {tr('on' if temp_auto_start else 'off')}", True, TEXT_COLOR), (auto_start_toggle_btn.x + 15, auto_start_toggle_btn.centery - 7))

                pygame.draw.rect(screen, ACCENT_COLOR, check_updates_btn, border_radius=8)
                screen.blit(font_main.render(tr("check_updates_now"), True, TEXT_COLOR), (check_updates_btn.x + 15, check_updates_btn.centery - 7))

            elif settings_tab == "appearance":
                screen.blit(font_subtitle.render(tr("theme"), True, TEXT_COLOR), (settings_content_rect.x + 30, settings_content_rect.y + 30))
                
                is_dark = (temp_theme == "dark")
                pygame.draw.rect(screen, ACCENT_COLOR if is_dark else CARD_BG, theme_dark_btn, border_radius=8)
                screen.blit(font_main.render(tr("theme_dark"), True, TEXT_COLOR), (theme_dark_btn.centerx - 24, theme_dark_btn.centery - 7))

                pygame.draw.rect(screen, ACCENT_COLOR if not is_dark else CARD_BG, theme_light_btn, border_radius=8)
                screen.blit(font_main.render(tr("theme_light"), True, TEXT_COLOR), (theme_light_btn.centerx - 26, theme_light_btn.centery - 7))

                screen.blit(font_subtitle.render(tr("accent_color"), True, TEXT_COLOR), (settings_content_rect.x + 30, settings_content_rect.y + 150))
                for idx, col in enumerate(DEFAULT_PRESETS):
                    c_rect = pygame.Rect(settings_content_rect.x + 30 + idx * 50, settings_content_rect.y + 180, 36, 36)
                    pygame.draw.rect(screen, col, c_rect, border_radius=18)
                    if temp_accent_idx == idx:
                        pygame.draw.rect(screen, TEXT_COLOR, c_rect, width=2, border_radius=18)

                custom_btn_rect = pygame.Rect(settings_content_rect.x + 30 + len(DEFAULT_PRESETS) * 50, settings_content_rect.y + 180, 36, 36)
                pygame.draw.rect(screen, temp_custom_color, custom_btn_rect, border_radius=18)
                pygame.draw.rect(screen, TEXT_COLOR if temp_accent_idx == len(DEFAULT_PRESETS) else BORDER_COLOR, custom_btn_rect, width=2, border_radius=18)
                plus_surf = font_main.render("+", True, TEXT_COLOR)
                screen.blit(plus_surf, (custom_btn_rect.centerx - plus_surf.get_width() // 2, custom_btn_rect.centery - plus_surf.get_height() // 2))


                screen.blit(font_subtitle.render(tr("module_background"), True, TEXT_COLOR), (settings_content_rect.x + 30, settings_content_rect.y + 225))
                pygame.draw.rect(screen, ACCENT_COLOR if temp_bg_mode == "none" else CARD_BG, bg_none_btn, border_radius=8)
                screen.blit(font_main.render(tr("bg_none"), True, TEXT_COLOR), (bg_none_btn.centerx - 30, bg_none_btn.centery - 7))

                pygame.draw.rect(screen, ACCENT_COLOR if temp_bg_mode == "custom" else CARD_BG, bg_custom_btn, border_radius=8)
                screen.blit(font_main.render(tr("upload_photo"), True, TEXT_COLOR), (bg_custom_btn.centerx - 50, bg_custom_btn.centery - 7))

                bg_files = [f for f in os.listdir(BACKGROUNDS_DIR) if f.lower().endswith(".png")]
                for p_idx, bg_f in enumerate(bg_files):
                    p_name = os.path.splitext(bg_f)[0]
                    p_btn_rect = pygame.Rect(settings_content_rect.x + 30 + (p_idx % 5) * 85, settings_content_rect.y + 295 + (p_idx // 5) * 35, 75, 28)
                    is_sel_bg = (temp_bg_mode == "preset" and temp_bg_preset == p_name)
                    pygame.draw.rect(screen, ACCENT_COLOR if is_sel_bg else CARD_BG, p_btn_rect, border_radius=6)
                    pygame.draw.rect(screen, BORDER_COLOR, p_btn_rect, width=1, border_radius=6)
                    screen.blit(font_small.render(p_name, True, TEXT_COLOR), (p_btn_rect.centerx - font_small.size(p_name)[0]//2, p_btn_rect.centery - 6))
                # --- Вибір кольору узора фону ---
                screen.blit(
                    font_small.render(tr("bg_pattern_color"), True, GRAY_TEXT),
                    (settings_content_rect.x + 30, settings_content_rect.y + 335)
                )

                for idx, col in enumerate(DEFAULT_PRESETS):
                    c_rect = pygame.Rect(
                        settings_content_rect.x + 30 + (idx * 50),
                        settings_content_rect.y + 360,
                        36,
                        36
                    )
                    pygame.draw.rect(screen, col, c_rect, border_radius=8)
                    if temp_bg_pattern_color == col:
                        pygame.draw.rect(screen, TEXT_COLOR, c_rect, width=2, border_radius=8)

                bg_custom_color_rect = pygame.Rect(
                    settings_content_rect.x + 30 + len(DEFAULT_PRESETS) * 50,
                    settings_content_rect.y + 360, 36, 36
                )
                pygame.draw.rect(screen, temp_bg_pattern_color, bg_custom_color_rect, border_radius=8)
                pygame.draw.rect(screen, TEXT_COLOR if bg_color_picker_open else BORDER_COLOR, bg_custom_color_rect, width=2, border_radius=8)
                plus_surf = font_main.render("+", True, TEXT_COLOR)
                screen.blit(plus_surf, (bg_custom_color_rect.centerx - plus_surf.get_width() // 2, bg_custom_color_rect.centery - plus_surf.get_height() // 2))

                # --- Випадаючий пікер кольору (якщо відкритий) ---
                if bg_color_picker_open:
                    # Змістимо його нижче або зробимо так, щоб він не перекривав узори, 
                    # або перевіримо чи заданий правильно PICKER_SIZE
                    bg_picker_rect = pygame.Rect(
                        settings_content_rect.x + 30,
                        settings_content_rect.y + 410,  # Опустили нижче узорів (було 230)
                        PICKER_SIZE + 20,
                        PICKER_SIZE + 20
                    )
                    dim = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
                    dim.fill((0, 0, 0, 120))
                    screen.blit(dim, (0, 0))
                    pygame.draw.rect(screen, PANEL_BG, bg_picker_rect, border_radius=10)
                    pygame.draw.rect(screen, BORDER_COLOR, bg_picker_rect, width=2, border_radius=10)
                    if picker_surface:
                        screen.blit(picker_surface, (bg_picker_rect.x + 10, bg_picker_rect.y + 10))
                    close_rect = pygame.Rect(bg_picker_rect.x + 4, bg_picker_rect.y + 4, 24, 24)
                    pygame.draw.rect(screen, DANGER_COLOR, close_rect, border_radius=6)
                    close_surf = font_main.render("×", True, TEXT_COLOR)
                    screen.blit(close_surf, (close_rect.centerx - close_surf.get_width() // 2, close_rect.centery - close_surf.get_height() // 2))

                # --- Кнопка редагування сітки ---
                # Теж опускаємо нижче, щоб вона не зливалася з пікером
                toggle_edit_layout_btn.y = settings_content_rect.y + 430 + (PICKER_SIZE if bg_color_picker_open else 0)

                pygame.draw.rect(screen, CARD_BG, toggle_edit_layout_btn, border_radius=8)
                pygame.draw.rect(screen, BORDER_COLOR, toggle_edit_layout_btn, width=1, border_radius=8)
                screen.blit(
                    font_main.render(tr("edit_grid"), True, TEXT_COLOR),
                    (toggle_edit_layout_btn.x + 15, toggle_edit_layout_btn.y + 12)
                )
                pygame.draw.rect(screen, ACCENT_COLOR, toggle_edit_layout_btn, border_radius=8)
                screen.blit(font_main.render(f"⚙ {tr('edit_grid')}", True, TEXT_COLOR), (toggle_edit_layout_btn.centerx - 110, toggle_edit_layout_btn.centery - 7))
                if color_picker_open:
                    # Модальное окно выбора основного цвета.
                    dim = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
                    dim.fill((0, 0, 0, 120))
                    screen.blit(dim, (0, 0))
                    pygame.draw.rect(screen, PANEL_BG, picker_rect, border_radius=10)
                    pygame.draw.rect(screen, BORDER_COLOR, picker_rect, width=2, border_radius=10)
                    if picker_surface:
                        screen.blit(picker_surface, (picker_rect.x + 10, picker_rect.y + 10))
                    close_rect = pygame.Rect(picker_rect.x + 4, picker_rect.y + 4, 24, 24)
                    pygame.draw.rect(screen, DANGER_COLOR, close_rect, border_radius=6)
                    close_surf = font_main.render("×", True, TEXT_COLOR)
                    screen.blit(close_surf, (close_rect.centerx - close_surf.get_width() // 2, close_rect.centery - close_surf.get_height() // 2))
        pygame.display.flip()
        clock.tick(60)