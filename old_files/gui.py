# ==========================================
# Sector 1 "Imports & App Initialization"
# ==========================================
import sys
import os
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
import re
import pygame
from launcher_core import (get_installed_versions, get_available_minecraft_versions, start_minecraft, is_game_running, stop_minecraft, create_new_version, update_version, update_client, update_jar, backup_version, restore_version_backup, delete_modpack, list_version_backups, MINECRAFT_DIR)



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
accent_idx = 0
custom_color = (255, 0, 128)
ram_gb = 4
ram_protection = True
launch_action = "close"
auto_backup_enabled = False
skin_path = ""
grid_weights_w = [1.0, 1.5, 1.0]
grid_weights_h = [1.0, 1.2]
detached_modules = []
active_processes = {}
module_layouts = {}
logs = ["[System] Многооконная система модулей активна.", "[System] Кнопка ↗ открывает отдельное окно Pygame."]

# Настройки фона модулей
bg_mode = "preset"           
bg_preset = "bg-1"           
bg_custom_path = ""          
bg_pattern_color = (88, 101, 242) 

versions_scroll_offset = 0
mods_scroll_offset = 0
mod_browser_scroll_offset = 0

frametime_history = []
fps_history = []
game_session_start = None


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
        "accent_idx": accent_idx,
        "custom_color": list(custom_color),
        "ram_gb": ram_gb,
        "ram_protection": ram_protection,
        "launch_action": launch_action,
        "auto_backup_enabled": auto_backup_enabled,
        "skin_path": skin_path,
        "grid_weights_w": grid_weights_w,
        "grid_weights_h": grid_weights_h,
        "detached_modules": detached_modules,
        "module_layouts": module_layouts,
        "bg_mode": bg_mode,
        "bg_preset": bg_preset,
        "bg_custom_path": bg_custom_path,
        "bg_pattern_color": list(bg_pattern_color),
    }
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4, ensure_ascii=False)
    except (OSError, TypeError) as error:
        print(f"Ошибка сохранения конфигурации: {error}")
        return False
    return True


def add_log(message):
    logs.append(str(message))
    if shared_logs_manager is not None:
        shared_logs_manager.append(str(message))


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
modrinth_download_status = "Ожидание ввода..."

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

def search_modrinth_projects(
    query, mc_version="1.20.1", loader="fabric", sort_asc=True
):
  """Пошук модів через Modrinth API без ризику отримати HTTP 400"""
  try:
    clean_query = query.strip() if query else "minecraft"
    q_enc = urllib.parse.quote(clean_query)

    # Робимо запит за назвою без каппризних фасетів,
    # що гарантує відсутність помилки 400 і видає всі реальні моди з сайту
    url = f"https://api.modrinth.com/v2/search?query={q_enc}&limit=25"

    headers = {
        "User-Agent": (
            "Kuvanty/MaceLauncher/1.0 (Contact: kuvanty.dev@gmail.com;"
            " https://github.com/Kuvanty/MaceLauncher)"
        )
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=8) as response:
      data = json.loads(response.read().decode("utf-8"))
      return data.get("hits", [])
  except Exception as e:
    print(f"Помилка пошуку Modrinth: {e}")
    return []

def download_modrinth_project(slug, mc_version, mods_dir):
    global modrinth_download_status
    modrinth_download_status = f"Поиск '{slug}' на Modrinth..."
    try:
        url = f"https://api.modrinth.com/v2/project/{slug}/version"
        req = urllib.request.Request(url, headers={'User-Agent': 'MaceLauncher/1.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        valid_file_url = None
        file_name = None
        
        for ver in data:
            if mc_version in ver.get("game_versions", []):
                files = ver.get("files", [])
                if files:
                    valid_file_url = files[0]["url"]
                    file_name = files[0]["filename"]
                    break
        
        if valid_file_url:
            modrinth_download_status = f"Скачивание {file_name}..."
            if not os.path.exists(mods_dir):
                os.makedirs(mods_dir, exist_ok=True)
            dest = os.path.join(mods_dir, file_name)
            urllib.request.urlretrieve(valid_file_url, dest)
            modrinth_download_status = f"Успешно установлено: {file_name}!"
        else:
            modrinth_download_status = f"Ошибка: нет версии мода для {mc_version}!"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            modrinth_download_status = f"Ошибка: Мод '{slug}' не найден!"
        else:
            modrinth_download_status = f"HTTP Ошибка: {e.code}"
    except Exception as e:
        modrinth_download_status = f"Ошибка скачивания: {e}"

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
        scaled = pygame.transform.smoothscale(tile, (screen_w, screen_h))
        scaled.set_alpha(90)
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
    sys_font = UI_FONT if UI_FONT.lower().replace(" ", "") in pygame.font.get_fonts() else "Verdana"
    font_title = pygame.font.SysFont(sys_font, 22, bold=True)
    font_subtitle = pygame.font.SysFont(sys_font, 16, bold=True)
    font_main = pygame.font.SysFont(sys_font, 14, bold=True)
    font_small = pygame.font.SysFont(sys_font, 12, bold=True)
    font_console = pygame.font.SysFont("Consolas", 11, bold=False)
    font_clock = pygame.font.SysFont(sys_font, 24, bold=True)

def load_skin_file(path):
    global loaded_skin_surface
    if path and os.path.exists(path):
        try:
            loaded_skin_surface = pygame.image.load(path).convert_alpha()
            return True
        except Exception as e:
            print(f"Ошибка загрузки скина: {e}")
    loaded_skin_surface = None
    return False

def render_skin_head(size=36):
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
    return surf

def get_hardware_info():
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

    return {
        "cpu_name": cpu_name, "cpu_usage": cpu_usage, "cpu_temp": cpu_temp,
        "gpu_name": gpu_name, "gpu_usage": gpu_usage, "gpu_temp": gpu_temp,
        "ram_model": ram_model, "ram_count": ram_count, "ram_usage": ram_usage_pct, "ram_temp": ram_temp
    }

def draw_info_module_content(surface, rect, cur_fps):
    if rect.height < 150:
        header_surf = font_small.render("СИСТЕМА И ВРЕМЯ", True, GRAY_TEXT)
        surface.blit(header_surf, (rect.x + 10, rect.y + 6))
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        time_surf = font_subtitle.render(now_str, True, ACCENT_COLOR)
        surface.blit(time_surf, (rect.x + 10, rect.y + 22))
        fps_text = f"FPS: {int(cur_fps)} | Загрузка RAM: {get_hardware_info()['ram_usage']}%"
        surface.blit(font_small.render(fps_text, True, TEXT_COLOR), (rect.x + 10, rect.y + 48))
        return

    header_surf = font_small.render("СИСТЕМА И ВРЕМЯ", True, GRAY_TEXT)
    surface.blit(header_surf, (rect.x + 12, rect.y + 8))

    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    time_surf = font_clock.render(now_str, True, ACCENT_COLOR)
    surface.blit(time_surf, (rect.x + 12, rect.y + 24))

    global game_session_start
    if is_game_running():
        if game_session_start is None:
            game_session_start = time.time()
        elapsed = int(time.time() - game_session_start)
        hrs = elapsed // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        session_str = f"Сессия: {hrs:02d}:{mins:02d}:{secs:02d}"
        session_color = SUCCESS_COLOR
    else:
        game_session_start = None
        session_str = "Сессия: Не в игре"
        session_color = GRAY_TEXT

    sess_surf = font_small.render(session_str, True, session_color)
    surface.blit(sess_surf, (rect.x + 12, rect.y + 54))

    avg_fps = int(sum(fps_history) / len(fps_history)) if fps_history else int(cur_fps)
    min_fps = int(min(fps_history)) if fps_history else int(cur_fps)
    max_fps = int(max(fps_history)) if fps_history else int(cur_fps)
    tps_val = 20.0 if is_game_running() else 0.0

    fps_text = f"FPS: {int(cur_fps)} (Ср:{avg_fps} Min:{min_fps} Max:{max_fps}) | TPS: {tps_val:.1f}"
    fps_surf = font_small.render(fps_text, True, TEXT_COLOR)
    surface.blit(fps_surf, (rect.x + 12, rect.y + 72))

    sep_y = rect.y + 92
    if sep_y + 10 < rect.bottom:
        pygame.draw.line(surface, BORDER_COLOR, (rect.x + 10, sep_y), (rect.right - 10, sep_y), 1)

    hw_info = get_hardware_info()

    def get_status_data(usage):
        if usage < 25:
            return "Хорошо", (40, 167, 69)
        elif usage < 50:
            return "Нормально", (173, 255, 47)
        elif usage < 60:
            return "Среднее", (255, 193, 7)
        elif usage < 80:
            return "Тяжеловато", (253, 126, 20)
        else:
            return "Очень тяжело", (220, 53, 69)

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
        info_str = f"Нагрузка: {usage}% | Темп: {temp}"
        surface.blit(font_console.render(info_str, True, GRAY_TEXT), (rect.x + 12, row_y))
        
        status_surf = font_console.render(status_txt, True, status_col)
        surface.blit(status_surf, (rect.right - 12 - status_surf.get_width(), row_y))
        
        row_y += 22

    ram_name = f"{hw_info['ram_model']} ({hw_info['ram_count']} шт.)"

    draw_vertical_block("CPU", hw_info["cpu_name"], cpu_usage, hw_info["cpu_temp"], cpu_status_txt, cpu_status_col)
    draw_vertical_block("GPU", hw_info["gpu_name"], gpu_usage, hw_info["gpu_temp"], gpu_status_txt, gpu_status_col)
    draw_vertical_block("RAM", ram_name, ram_usage, hw_info["ram_temp"], ram_status_txt, ram_status_col)

# ==========================================
# MOD FILTER PROCESS WINDOW
# ==========================================
def run_mod_filter_process(theme, shared_filter_data, available_versions):
    """Отдельное окно Pygame с фильтрами модов (версия, загрузчик, сортировка А-Я/Я-А)[cite: 1]"""
    try:
        pygame.init()
        sub_screen = pygame.display.set_mode((420, 480))
        pygame.display.set_caption("Mace Launcher - Фильтры модов")
        
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

            sub_screen.blit(font_subtitle.render("Фильтры браузера модов", True, text_c), (30, 20))
            
            # Версия игры (кнопка для открытия списка с ползунком)[cite: 1]
            sub_screen.blit(font_small.render("ВЕРСИЯ ИГРЫ", True, GRAY_TEXT), (30, 60))
            ver_btn = pygame.Rect(30, 80, 360, 40)
            pygame.draw.rect(sub_screen, card_c, ver_btn, border_radius=8)
            pygame.draw.rect(sub_screen, BORDER_COLOR, ver_btn, width=1, border_radius=8)
            sub_screen.blit(font_main.render(f"Выбрана: {cur_ver} (Нажми для выбора)", True, text_c), (ver_btn.x + 12, ver_btn.y + 11))

            # Загрузчик (кнопка для открытия списка с ползунком)[cite: 1]
            sub_screen.blit(font_small.render("ЗАГРУЗЧИК", True, GRAY_TEXT), (30, 140))
            loader_btn = pygame.Rect(30, 160, 360, 40)
            pygame.draw.rect(sub_screen, card_c, loader_btn, border_radius=8)
            pygame.draw.rect(sub_screen, BORDER_COLOR, loader_btn, width=1, border_radius=8)
            sub_screen.blit(font_main.render(f"Загрузчик: {cur_loader.upper()}", True, text_c), (loader_btn.x + 12, loader_btn.y + 11))

            # От А до Я (кнопка-свич. Меняется название на "От Я до А")[cite: 1]
            sub_screen.blit(font_small.render("ПОРЯДОК СОРТИРОВКИ", True, GRAY_TEXT), (30, 220))
            sort_btn = pygame.Rect(30, 240, 360, 40)
            pygame.draw.rect(sub_screen, card_c, sort_btn, border_radius=8)
            pygame.draw.rect(sub_screen, BORDER_COLOR, sort_btn, width=1, border_radius=8)
            sort_text = "Сортировка: От А до Я" if cur_sort_asc else "Сортировка: От Я до А"
            sub_screen.blit(font_main.render(sort_text, True, text_c), (sort_btn.x + 12, sort_btn.y + 11))

            # В самом низу надпись "моды будут установлены на версию: " выбранная версия[cite: 1]
            bottom_rect = pygame.Rect(30, 410, 360, 50)
            pygame.draw.rect(sub_screen, PANEL_BG, bottom_rect, border_radius=8)
            pygame.draw.rect(sub_screen, ACCENT_COLOR, bottom_rect, width=1, border_radius=8)
            target_str = f"моды будут установлены на версию: {cur_ver}"
            sub_screen.blit(font_small.render(target_str, True, SUCCESS_COLOR), (bottom_rect.x + 12, bottom_rect.centery - 8))

            # Выпадающий список версий с ползунком
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

            # Выпадающий список загрузчиков
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
        print(f"Ошибка в окне фильтров: {e}")

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
        status_message = "Введіть назву збірки та оберіть параметри."
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
                            status_message = "Помилка: Ім'я версії не може бути порожнім!"
                            status_color = DANGER_COLOR
                            continue

                        version_folder = os.path.join(MINECRAFT_DIR, "versions", ver_name_input.strip())
                        if os.path.exists(version_folder):
                            status_message = f"ЗАХИСТ: Версія '{ver_name_input}' вже існує! Не створено."
                            status_color = DANGER_COLOR
                            continue

                        selected_mc_version = available_versions[mc_version_idx]
                        status_message = "Створення нових файлів та папок збірки..."
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

            title = font_subtitle.render("Створення нової версії / модпака", True, text_c)
            sub_screen.blit(title, (margin, 22))

            sub_screen.blit(font_small.render("НАЗВА ВЕРСІЇ (ЗАХИСТ ВІД ДУБЛІКАТІВ)", True, GRAY_TEXT), (margin, 58))
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

            sub_screen.blit(font_small.render("ВЕРСІЯ MINECRAFT — виберіть зі списку", True, GRAY_TEXT), (margin, 146))
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
                f"Выбрано: Minecraft {available_versions[mc_version_idx]}",
                True,
                SUCCESS_COLOR,
            )
            sub_screen.blit(selected_caption, (margin, ribbon_rect.bottom + 8))

            sub_screen.blit(font_small.render("ЗАВАНТАЖЧИК", True, GRAY_TEXT), (margin, loader_label_y))
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
            sub_screen.blit(font_small.render("УВАГА: Будуть створені нові файли та папки збірки!", True, DANGER_COLOR), (warn_rect.x + 12, warn_rect.y + 9))
            sub_screen.blit(font_small.render("Захист: якщо папка з такою назвою вже існує,", True, GRAY_TEXT), (warn_rect.x + 12, warn_rect.y + 31))
            sub_screen.blit(font_small.render("створення буде повністю заблоковано для безпеки.", True, GRAY_TEXT), (warn_rect.x + 12, warn_rect.y + 49))

            status_surf = font_small.render(status_message, True, status_color)
            sub_screen.blit(status_surf, (status_rect.x, status_rect.y))

            pygame.draw.rect(sub_screen, SUCCESS_COLOR, create_btn, border_radius=8)
            btn_txt = font_title.render("СТВОРИТИ ВЕРСІЮ", True, text_c)
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
            question = font_title.render("Точно ли ты этого хочешь?", True, text_c)
            sub_screen.blit(question, (panel.centerx - question.get_width() // 2, 72))
            version_s = font_main.render(f"Версия: {version_name}", True, text_c)
            sub_screen.blit(version_s, (panel.centerx - version_s.get_width() // 2, 112))
            detail_s = font_small.render(details[:72], True, gray_c)
            sub_screen.blit(detail_s, (panel.centerx - detail_s.get_width() // 2, 140))
            pygame.draw.rect(sub_screen, DANGER_COLOR, yes_rect, border_radius=8)
            pygame.draw.rect(sub_screen, BORDER_COLOR, no_rect, width=1, border_radius=8)
            yes_s = font_main.render("Да, продолжить", True, TEXT_COLOR)
            no_s = font_main.render("Нет", True, text_c)
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
    manager = multiprocessing.Manager()
    result = manager.dict()
    result["confirmed"] = False
    p = multiprocessing.Process(
        target=run_confirmation_process,
        args=(theme, VERSION_ACTION_LABELS.get(action_key, action_key), version_name, details, result),
    )
    p.start()
    p.join()
    confirmed = bool(result.get("confirmed", False))
    manager.shutdown()
    return confirmed


def run_version_editor_process(theme, version_name, shared_logs):
    """Отдельное окно Pygame для управления выбранным модпаком."""
    try:
        pygame.init()
        sub_screen = pygame.display.set_mode((760, 700), pygame.RESIZABLE)
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

        status_message = "Выберите действие."
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

            title = font_title.render("Редактирование версии", True, text_c)
            sub_screen.blit(title, (margin, 22))
            ver_title = font_subtitle.render(version_name, True, ACCENT_COLOR)
            sub_screen.blit(ver_title, (margin, 52))

            sub_screen.blit(font_small.render("ЦЕЛЕВАЯ ВЕРСИЯ MINECRAFT", True, gray_c), (margin, 78))
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
            sub_screen.blit(font_small.render("ОБНОВИТЬ ВЕРСИЮ", True, gray_c), (update_card.x + 12, update_card.y + 10))
            pygame.draw.rect(sub_screen, SUCCESS_COLOR, update_btn, border_radius=8)
            update_text = font_main.render("Обновить", True, TEXT_COLOR)
            sub_screen.blit(update_text, (update_btn.centerx - update_text.get_width() // 2, update_btn.centery - update_text.get_height() // 2))

            selected_label = font_main.render(f"до Minecraft {available_versions[target_idx]}", True, text_c)
            sub_screen.blit(selected_label, (update_label_x, update_btn.centery - selected_label.get_height() // 2))

            pygame.draw.rect(sub_screen, card_c, client_card, border_radius=12)
            pygame.draw.rect(sub_screen, BORDER_COLOR, client_card, width=1, border_radius=12)
            sub_screen.blit(font_small.render("ОБНОВИТЬ КЛИЕНТ", True, gray_c), (client_card.x + 12, client_card.y + 10))
            pygame.draw.rect(sub_screen, ACCENT_COLOR, client_btn, border_radius=8)
            pygame.draw.rect(sub_screen, ACCENT_COLOR, jar_btn, border_radius=8)
            client_s = font_main.render("Обновить клиент", True, TEXT_COLOR)
            jar_s = font_main.render("Обновить JAR", True, TEXT_COLOR)
            sub_screen.blit(client_s, (client_btn.centerx - client_s.get_width() // 2, client_btn.centery - client_s.get_height() // 2))
            sub_screen.blit(jar_s, (jar_btn.centerx - jar_s.get_width() // 2, jar_btn.centery - jar_s.get_height() // 2))

            pygame.draw.rect(sub_screen, card_c, backup_card, border_radius=12)
            pygame.draw.rect(sub_screen, BORDER_COLOR, backup_card, width=1, border_radius=12)
            sub_screen.blit(font_small.render("РЕЗЕРВНАЯ КОПИЯ", True, gray_c), (backup_card.x + 12, backup_card.y + 10))
            pygame.draw.rect(sub_screen, SUCCESS_COLOR, backup_btn, border_radius=8)
            pygame.draw.rect(sub_screen, card_c, restore_btn, border_radius=8)
            pygame.draw.rect(sub_screen, BORDER_COLOR, restore_btn, width=1, border_radius=8)
            backup_s = font_main.render("Сделать бэкап", True, TEXT_COLOR)
            restore_s = font_main.render("Восстановить", True, text_c)
            sub_screen.blit(backup_s, (backup_btn.centerx - backup_s.get_width() // 2, backup_btn.centery - backup_s.get_height() // 2))
            sub_screen.blit(restore_s, (restore_btn.centerx - restore_s.get_width() // 2, restore_btn.centery - restore_s.get_height() // 2))

            pygame.draw.rect(sub_screen, DANGER_COLOR, delete_btn, border_radius=8)
            delete_s = font_main.render("Удалить мод-пак", True, TEXT_COLOR)
            sub_screen.blit(delete_s, (delete_btn.centerx - delete_s.get_width() // 2, delete_btn.centery - delete_s.get_height() // 2))

            pygame.draw.rect(sub_screen, card_c, status_box, border_radius=8)
            pygame.draw.rect(sub_screen, BORDER_COLOR, status_box, width=1, border_radius=8)
            status_s = font_small.render(status_message, True, status_color)
            sub_screen.blit(status_s, (status_box.x + 12, status_box.centery - status_s.get_height() // 2))

            pygame.draw.rect(sub_screen, card_c, close_btn, border_radius=8)
            pygame.draw.rect(sub_screen, BORDER_COLOR, close_btn, width=1, border_radius=8)
            close_s = font_main.render("Закрыть", True, text_c)
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
    pygame.display.set_caption("Mace Launcher - Multi-Window Edition")

    build_picker_surface()
    init_fonts()

    config = load_config()
    username = config.get("username", "Kwvanty")
    saved_version = config.get("last_version", "")
    current_theme = config.get("theme", "dark")
    accent_idx = config.get("accent_idx", 0)
    custom_color = tuple(config.get("custom_color", [255, 0, 128]))
    ram_gb = config.get("ram_gb", 4)
    ram_protection = config.get("ram_protection", True)
    launch_action = config.get("launch_action", "close")
    auto_backup_enabled = config.get("auto_backup_enabled", False)
    skin_path = config.get("skin_path", "")

    bg_mode = config.get("bg_mode", "preset")
    bg_preset = config.get("bg_preset", "bg-1")
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

    temp_bg_mode = bg_mode
    temp_bg_preset = bg_preset
    temp_bg_custom_path = bg_custom_path
    temp_bg_pattern_color = bg_pattern_color

    update_theme_colors()

    current_page = "main"          
    settings_tab = "general"       
    center_active_tab = "news"     # Вкладки внутри модуля "Новости и модпаки": "news", "modpacks", "browser"[cite: 1]

    input_active = False
    modrinth_input_active = False
    modrinth_input_text = ""
    mod_browser_search_text = ""
    mod_browser_search_active = False
    cached_mod_results = []
    last_browser_search_query = None
    
    versions = get_installed_versions()

    selected_ver_idx = get_newest_version_index(versions)
    if saved_version in versions:
        selected_ver_idx = versions.index(saved_version)

    if versions and selected_ver_idx != -1:
        shared_filter_dict["version"] = versions[selected_ver_idx]

    dropdown_open = False
    was_game_running = False
    color_picker_open = False
    bg_color_picker_open = False
    is_dragging_scrollbar = False
    is_dragging_mods_scrollbar = False
    is_dragging_browser_scrollbar = False

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
        main_area_w = cur_w - 20
        main_area_h = cur_h - 90 - TOP_BAR_HEIGHT

        total_w_weight = sum(grid_weights_w)
        available_w = main_area_w - 20
        col_widths = [int(available_w * (w / total_w_weight)) for w in grid_weights_w]

        total_h_weight = sum(grid_weights_h)
        available_h = main_area_h - 10
        row_heights = [int(available_h * (h / total_h_weight)) for h in grid_weights_h]

        col_x_coords = [10]
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
                grid_divider_rects_h.append((j, pygame.Rect(10, div_y, main_area_w, 10)))

        control_bar_rect = pygame.Rect(10, cur_h - 70, cur_w - 20, 60)
        
        root_minecraft_folder_btn = pygame.Rect(10, cur_h - 70, 48, 60)
        dropdown_rect = pygame.Rect(root_minecraft_folder_btn.right + 10, cur_h - 70, int(control_bar_rect.width * 0.35), 60)
        modpack_folder_btn = pygame.Rect(dropdown_rect.right + 10, cur_h - 70, 48, 60)
        create_version_btn = pygame.Rect(modpack_folder_btn.right + 10, cur_h - 70, 48, 60)
        edit_version_btn = pygame.Rect(create_version_btn.right + 10, cur_h - 70, 48, 60)
        launch_btn_rect = pygame.Rect(edit_version_btn.right + 10, cur_h - 70, (cur_w - 10) - (edit_version_btn.right + 10), 60)

        if "left" in module_rects and "left" not in detached_modules:
            l_r = module_rects["left"]
            profile_btn_rect = pygame.Rect(l_r.x + 15, l_r.y + 15, l_r.width - 30, 60)
            nav_main_btn = pygame.Rect(l_r.x + 15, profile_btn_rect.bottom + 10, l_r.width - 30, 36)
            nav_mods_btn = pygame.Rect(l_r.x + 15, nav_main_btn.bottom + 8, l_r.width - 30, 36)
            nav_settings_btn = pygame.Rect(l_r.x + 15, nav_mods_btn.bottom + 8, l_r.width - 30, 36)
        else:
            profile_btn_rect = nav_main_btn = nav_mods_btn = nav_settings_btn = pygame.Rect(0, 0, 0, 0)

        if "right" in module_rects and "right" not in detached_modules:
            r_r = module_rects["right"]
            skin_preview_box = pygame.Rect(r_r.x + 15, r_r.y + 40, r_r.width - 30, max(60, r_r.height - 135))
            change_skin_btn = pygame.Rect(r_r.x + 15, r_r.bottom - 85, r_r.width - 30, 36)
            reset_skin_btn = pygame.Rect(r_r.x + 15, r_r.bottom - 42, r_r.width - 30, 32)
        else:
            skin_preview_box = change_skin_btn = reset_skin_btn = pygame.Rect(0, 0, 0, 0)

        settings_back_btn = pygame.Rect(15, 65, 110, 38)
        settings_sidebar_rect = pygame.Rect(15, 115, 220, cur_h - 130)
        settings_content_rect = pygame.Rect(settings_sidebar_rect.right + 15, 115, cur_w - settings_sidebar_rect.width - 45, cur_h - 130)

        set_tab_general_btn = pygame.Rect(settings_sidebar_rect.x + 10, settings_sidebar_rect.y + 15, settings_sidebar_rect.width - 20, 40)
        set_tab_appearance_btn = pygame.Rect(settings_sidebar_rect.x + 10, settings_sidebar_rect.y + 65, settings_sidebar_rect.width - 20, 40)

        settings_apply_btn = pygame.Rect(settings_content_rect.right - 140, settings_content_rect.bottom - 55, 120, 40)
        settings_cancel_btn = pygame.Rect(settings_apply_btn.x - 130, settings_content_rect.bottom - 55, 120, 40)

        ram_minus_btn = pygame.Rect(settings_content_rect.x + 30, settings_content_rect.y + 95, 40, 40)
        ram_plus_btn = pygame.Rect(settings_content_rect.x + 180, settings_content_rect.y + 95, 40, 40)
        ram_protection_toggle_btn = pygame.Rect(settings_content_rect.x + 30, settings_content_rect.y + 145, 260, 36)
        action_toggle_btn = pygame.Rect(settings_content_rect.x + 30, settings_content_rect.y + 255, 260, 40)
        auto_backup_btn = pygame.Rect(settings_content_rect.x + 30, settings_content_rect.y + 315, 260, 40)

        theme_dark_btn = pygame.Rect(settings_content_rect.x + 30, settings_content_rect.y + 95, 120, 40)
        theme_light_btn = pygame.Rect(settings_content_rect.x + 160, settings_content_rect.y + 95, 120, 40)
        picker_rect = pygame.Rect(settings_content_rect.x + 30, settings_content_rect.y + 230, PICKER_SIZE + 20, PICKER_SIZE + 20)
        
        bg_none_btn = pygame.Rect(settings_content_rect.x + 30, settings_content_rect.y + 250, 160, 36)
        bg_custom_btn = pygame.Rect(settings_content_rect.x + 200, settings_content_rect.y + 250, 160, 36)
        
        toggle_edit_layout_btn = pygame.Rect(settings_content_rect.x + 30, settings_content_rect.y + 440, 280, 42)
        
        mods_back_btn = pygame.Rect(15, 65, 110, 38)
        mods_top_panel = pygame.Rect(15, 115, cur_w - 30, 80)
        mods_list_rect = pygame.Rect(15, 205, cur_w - 30, cur_h - 220)
        
        modrinth_search_rect = pygame.Rect(mods_top_panel.x + 15, mods_top_panel.y + 20, 250, 40)
        modrinth_install_btn = pygame.Rect(modrinth_search_rect.right + 10, mods_top_panel.y + 20, 130, 40)
        
        mods_folder_btn = pygame.Rect(mods_top_panel.right - 60, mods_top_panel.y + 20, 40, 40)
        mods_copy_btn = pygame.Rect(mods_folder_btn.left - 50, mods_top_panel.y + 20, 40, 40)

        versions = get_installed_versions()
        cur_ver = versions[selected_ver_idx] if selected_ver_idx != -1 and len(versions) > 0 else ""
        mods_dir_path = os.path.join(MINECRAFT_DIR, "versions", cur_ver, "mods") if cur_ver else ""
        
        local_mods = []
        if mods_dir_path and os.path.exists(mods_dir_path):
            local_mods = [f for f in os.listdir(mods_dir_path) if f.endswith(".jar") or f.endswith(".jar.disabled")]

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
                    max_mod_scroll = max(0, len(local_mods) * 55 - (mods_list_rect.height - 20))
                    mods_scroll_offset = max(0, min(mods_scroll_offset, max_mod_scroll))
                elif current_page == "main" and "center" in module_layouts and "center" not in detached_modules and center_active_tab == "browser":
                    mod_browser_scroll_offset -= event.y * 40
                    max_b_scroll = max(0, len(cached_mod_results) * 65 - 200)
                    mod_browser_scroll_offset = max(0, min(mod_browser_scroll_offset, max_b_scroll))

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
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

                    # Проверка кликов по центру (вкладки Новости / Модпаки / Браузер модов)[cite: 1]
                    if "center" in module_rects and "center" not in detached_modules:
                        c_rect = module_rects["center"]
                        tab_news_rect = pygame.Rect(c_rect.x + 15, c_rect.y + 35, 90, 30)
                        tab_packs_rect = pygame.Rect(tab_news_rect.right + 8, c_rect.y + 35, 90, 30)
                        tab_browser_rect = pygame.Rect(tab_packs_rect.right + 8, c_rect.y + 35, 110, 30)

                        if tab_news_rect.collidepoint(event.pos):
                            center_active_tab = "news"
                        elif tab_packs_rect.collidepoint(event.pos):
                            center_active_tab = "modpacks"
                        elif tab_browser_rect.collidepoint(event.pos):
                            center_active_tab = "browser"

                        if center_active_tab == "browser":
                            search_box_rect = pygame.Rect(c_rect.x + 15, c_rect.y + 75, c_rect.width - 130, 36)
                            filter_btn_rect = pygame.Rect(search_box_rect.right + 10, c_rect.y + 75, 95, 36)

                            if search_box_rect.collidepoint(event.pos):
                                mod_browser_search_active = True
                            else:
                                mod_browser_search_active = False

                            if filter_btn_rect.collidepoint(event.pos):
                                add_log("[UI] Открытие окна фильтров модов.")
                                p_filt = multiprocessing.Process(
                                    target=run_mod_filter_process,
                                    args=(current_theme, shared_filter_dict, versions if versions else ["1.20.1"])
                                )
                                p_filt.start()

                            # Клик на кнопку установки мода в результатах поиска
                            y_start = c_rect.y + 125 - mod_browser_scroll_offset
                            for idx, mod_item in enumerate(cached_mod_results):
                                item_rect = pygame.Rect(c_rect.x + 15, y_start + idx * 65, c_rect.width - 30, 55)
                                install_btn_rect = pygame.Rect(item_rect.right - 90, item_rect.y + 12, 80, 30)
                                if install_btn_rect.collidepoint(event.pos):
                                    slug = mod_item.get("slug")
                                    target_v = shared_filter_dict.get("version", cur_ver)
                                    target_mods_dir = os.path.join(MINECRAFT_DIR, "versions", target_v, "mods") if target_v else mods_dir_path
                                    if slug and target_v:
                                        add_log(f"[ModBrowser] Установка мода {slug} для версий {target_v}")
                                        th = threading.Thread(target=download_modrinth_project, args=(slug, target_v, target_mods_dir))
                                        th.start()
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
                if dragged_module or resizing_module or resizing_grid_col is not None or resizing_grid_row is not None or is_dragging_scrollbar or is_dragging_mods_scrollbar:
                    dragged_module = None
                    resizing_module = None
                    resizing_grid_col = None
                    resizing_grid_row = None
                    is_dragging_scrollbar = False
                    is_dragging_mods_scrollbar = False
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
                if selected_ver_idx >= len(versions):
                    selected_ver_idx = max(0, len(versions) - 1)

                if current_page == "main" and not edit_layout_mode:
                    old_active = input_active
                    if "left" in module_rects and "left" not in detached_modules and profile_btn_rect.collidepoint(event.pos):
                        input_active = True
                    else:
                        input_active = False

                    if old_active and not input_active:
                        save_config(username, cur_ver)

                    if "left" in module_rects and "left" not in detached_modules:
                        if nav_main_btn.collidepoint(event.pos):
                            current_page = "main"
                        elif nav_mods_btn.collidepoint(event.pos):
                            current_page = "mods"
                        elif nav_settings_btn.collidepoint(event.pos):
                            current_page = "settings"
                            temp_theme = current_theme
                            temp_accent_idx = accent_idx
                            temp_custom_color = custom_color
                            temp_ram_gb = ram_gb
                            temp_ram_protection = ram_protection
                            temp_launch_action = launch_action
                            temp_auto_backup_enabled = auto_backup_enabled

                            temp_bg_mode = bg_mode
                            temp_bg_preset = bg_preset
                            temp_bg_custom_path = bg_custom_path
                            temp_bg_pattern_color = bg_pattern_color

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
                                selected_ver_idx = clicked_idx
                                save_config(username, versions[selected_ver_idx])
                                shared_filter_dict["version"] = versions[selected_ver_idx]
                                dropdown_open = False
                        else:
                            dropdown_open = False

                    if launch_btn_rect.collidepoint(event.pos):
                        if running_state:
                            stop_minecraft(log_func=add_log)
                        elif selected_ver_idx != -1:
                            save_config(username, cur_ver)
                            logs.clear()
                            if shared_logs_manager is not None:
                                shared_logs_manager[:] = []
                            add_log(f"[UI] Старт сессии {cur_ver} с RAM: {ram_gb}GB...")
                            
                            try:
                                start_minecraft(username, cur_ver, ram_gb=ram_gb, log_func=add_log)

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
                        modrinth_input_active = False

                    if modrinth_search_rect.collidepoint(event.pos):
                        modrinth_input_active = True
                    else:
                        modrinth_input_active = False
                    
                    if modrinth_install_btn.collidepoint(event.pos):
                        if modrinth_input_text.strip() and cur_ver:
                            mod_slug = modrinth_input_text.strip()
                            modrinth_input_text = ""
                            
                            thread = threading.Thread(target=download_modrinth_project, args=(mod_slug, cur_ver, mods_dir_path))
                            thread.start()

                    if mods_folder_btn.collidepoint(event.pos):
                        open_folder(mods_dir_path)
                    
                    if mods_copy_btn.collidepoint(event.pos):
                        names = [f.replace(".disabled", "") for f in local_mods]
                        copy_to_clipboard("\n".join(names))
                        modrinth_download_status = "Названия модов скопированы!"

                    visible_mods_rect = pygame.Rect(mods_list_rect.x, mods_list_rect.y, mods_list_rect.width - 20, mods_list_rect.height)
                    if visible_mods_rect.collidepoint(event.pos):
                        clicked_y = event.pos[1] - mods_list_rect.y - 10 + mods_scroll_offset
                        clicked_idx = int(clicked_y // 55)
                        
                        if 0 <= clicked_idx < len(local_mods):
                            mod_file = local_mods[clicked_idx]
                            mod_path = os.path.join(mods_dir_path, mod_file)
                            
                            item_y_actual = mods_list_rect.y + 10 + (clicked_idx * 55) - mods_scroll_offset
                            del_btn = pygame.Rect(mods_list_rect.right - 100, item_y_actual + 10, 80, 30)
                            toggle_btn = pygame.Rect(mods_list_rect.right - 190, item_y_actual + 10, 80, 30)

                            if del_btn.collidepoint(event.pos):
                                try:
                                    os.remove(mod_path)
                                except Exception as e:
                                    print(f"Помилка видалення: {e}")
                            elif toggle_btn.collidepoint(event.pos):
                                try:
                                    if mod_file.endswith(".disabled"):
                                        new_name = mod_file.replace(".disabled", "")
                                    else:
                                        new_name = mod_file + ".disabled"
                                    os.rename(mod_path, os.path.join(mods_dir_path, new_name))
                                except Exception as e:
                                    print(f"Помилка перейменування: {e}")

                    max_mod_scroll = max(0, len(local_mods) * 55 - (mods_list_rect.height - 20))
                    if max_mod_scroll > 0:
                        mods_scrollbar_track = pygame.Rect(mods_list_rect.right - 12, mods_list_rect.y + 5, 8, mods_list_rect.height - 10)
                        if mods_scrollbar_track.collidepoint(event.pos):
                            is_dragging_mods_scrollbar = True

                elif current_page == "settings":
                    if settings_back_btn.collidepoint(event.pos):
                        current_page = "main"
                        color_picker_open = False
                        bg_color_picker_open = False

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
                        bg_mode = temp_bg_mode
                        bg_preset = temp_bg_preset
                        bg_custom_path = temp_bg_custom_path
                        bg_pattern_color = temp_bg_pattern_color
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

                        if ram_minus_btn.collidepoint(event.pos) and temp_ram_gb > 2:
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

                    elif settings_tab == "appearance":
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

                        elif toggle_edit_layout_btn.collidepoint(event.pos):
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

                        if color_picker_open:
                            px_rel_x = event.pos[0] - (picker_rect.x + 10)
                            px_rel_y = event.pos[1] - (picker_rect.y + 10)
                            if 0 <= px_rel_x < PICKER_SIZE and 0 <= px_rel_y < PICKER_SIZE:
                                hue = px_rel_x / PICKER_SIZE
                                sat = 1.0 - (px_rel_y / PICKER_SIZE)
                                r, g, b = colorsys.hsv_to_rgb(hue, sat, 1.0)
                                temp_custom_color = (int(r * 255), int(g * 255), int(b * 255))
                                temp_accent_idx = len(DEFAULT_PRESETS)

                        bg_picker_rect = pygame.Rect(settings_content_rect.x + 30, settings_content_rect.y + 230, PICKER_SIZE + 20, PICKER_SIZE + 20)
                        if bg_color_picker_open:
                            px_rel_x = event.pos[0] - (bg_picker_rect.x + 10)
                            px_rel_y = event.pos[1] - (bg_picker_rect.y + 10)
                            if 0 <= px_rel_x < PICKER_SIZE and 0 <= px_rel_y < PICKER_SIZE:
                                hue = px_rel_x / PICKER_SIZE
                                sat = 1.0 - (px_rel_y / PICKER_SIZE)
                                r, g, b = colorsys.hsv_to_rgb(hue, sat, 1.0)
                                temp_bg_pattern_color = (int(r * 255), int(g * 255), int(b * 255))

            if event.type == pygame.KEYDOWN:
                if current_page == "main":
                    if edit_layout_mode and event.key == pygame.K_ESCAPE:
                        edit_layout_mode = False
                    elif input_active:
                        if event.key == pygame.K_BACKSPACE:
                            username = username[:-1]
                        elif event.key == pygame.K_RETURN:
                            input_active = False
                            save_config(username, cur_ver)
                        elif len(username) < 16 and event.unicode.isprintable():
                            username += event.unicode
                    elif center_active_tab == "browser" and mod_browser_search_active:
                        if event.key == pygame.K_BACKSPACE:
                            mod_browser_search_text = mod_browser_search_text[:-1]
                        elif event.key == pygame.K_RETURN:
                            pass
                        elif event.unicode.isprintable():
                            mod_browser_search_text += event.unicode
                        
                        # Живой поиск по первым буквам[cite: 1]
                        search_key = (mod_browser_search_text, shared_filter_dict.get("version"), shared_filter_dict.get("loader"), shared_filter_dict.get("sort_asc"))
                        if search_key != last_browser_search_query:
                            last_browser_search_query = search_key
                            cached_mod_results = search_modrinth_projects(
                                mod_browser_search_text,
                                shared_filter_dict.get("version", "1.20.1"),
                                shared_filter_dict.get("loader", "fabric"),
                                shared_filter_dict.get("sort_asc", True)
                            )

                elif current_page == "mods" and modrinth_input_active:
                    if event.key == pygame.K_BACKSPACE:
                        modrinth_input_text = modrinth_input_text[:-1]
                    elif event.key == pygame.K_RETURN:
                        if modrinth_input_text.strip() and cur_ver:
                            mod_slug = modrinth_input_text.strip()
                            modrinth_input_text = ""
                            thread = threading.Thread(target=download_modrinth_project, args=(mod_slug, cur_ver, mods_dir_path))
                            thread.start()
                    elif event.unicode.isprintable():
                        modrinth_input_text += event.unicode

        screen.fill(BG_COLOR)

        TOP_BAR_HEIGHT = 48
        top_bar_rect = pygame.Rect(10, 10, cur_w - 20, TOP_BAR_HEIGHT - 6)
        pygame.draw.rect(screen, PANEL_BG, top_bar_rect, border_radius=10)
        pygame.draw.rect(screen, BORDER_COLOR, top_bar_rect, width=1, border_radius=10)
        
        logo_reserved_x = top_bar_rect.x + 15
        header_title_surf = font_subtitle.render("Mace Launcher - Minecraft assembler", True, TEXT_COLOR)
        screen.blit(header_title_surf, (logo_reserved_x + 36, top_bar_rect.y + (top_bar_rect.height - header_title_surf.get_height()) // 2))

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

                        det_surf = font_main.render(f"Модуль [{mod_id.upper()}] в окне", True, GRAY_TEXT)
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
                    p_bg = INPUT_BG if not profile_btn_rect.collidepoint(mouse_pos) else CARD_BG
                    pygame.draw.rect(screen, p_bg, profile_btn_rect, border_radius=10)
                    pygame.draw.rect(screen, ACCENT_COLOR if input_active else BORDER_COLOR, profile_btn_rect, width=2 if input_active else 1, border_radius=10)

                    head_icon = render_skin_head(size=36)
                    head_y = profile_btn_rect.y + (profile_btn_rect.height - 36) // 2
                    screen.blit(head_icon, (profile_btn_rect.x + 12, head_y))

                    nick_surf = font_main.render(username + ("|" if input_active else ""), True, TEXT_COLOR)
                    nick_y = profile_btn_rect.y + (profile_btn_rect.height - nick_surf.get_height()) // 2
                    screen.blit(nick_surf, (profile_btn_rect.x + 58, nick_y))

                    pygame.draw.rect(screen, ACCENT_COLOR, nav_main_btn, border_radius=8)
                    pygame.draw.rect(screen, BORDER_COLOR, nav_main_btn, width=1, border_radius=8)
                    screen.blit(font_main.render("Обзор", True, TEXT_COLOR), (nav_main_btn.x + 15, nav_main_btn.y + 8))

                    pygame.draw.rect(screen, CARD_BG, nav_mods_btn, border_radius=8)
                    pygame.draw.rect(screen, BORDER_COLOR, nav_mods_btn, width=1, border_radius=8)
                    screen.blit(font_main.render("Моды", True, TEXT_COLOR), (nav_mods_btn.x + 15, nav_mods_btn.y + 8))

                    pygame.draw.rect(screen, CARD_BG, nav_settings_btn, border_radius=8)
                    pygame.draw.rect(screen, BORDER_COLOR, nav_settings_btn, width=1, border_radius=8)
                    screen.blit(font_main.render("Настройки", True, TEXT_COLOR), (nav_settings_btn.x + 15, nav_settings_btn.y + 8))

                elif mod_id == "info":
                    draw_info_module_content(screen, p_rect, cur_fps)

                elif mod_id == "console":
                    screen.blit(font_small.render("КОНСОЛЬ СИСТЕМЫ", True, GRAY_TEXT), (p_rect.x + 15, p_rect.y + 12))

                    console_box = pygame.Rect(p_rect.x + 12, p_rect.y + 35, p_rect.width - 24, p_rect.height - 47)
                    pygame.draw.rect(screen, INPUT_BG, console_box, border_radius=8)
                    pygame.draw.rect(screen, BORDER_COLOR, console_box, width=1, border_radius=8)

                    max_visible_lines = max(2, (console_box.height - 10) // 18)
                    visible_logs = logs[-max_visible_lines:]
                    
                    y_offset = console_box.y + 8
                    for line in visible_logs:
                        max_chars = max(8, (console_box.width - 20) // 8)
                        if len(line) > max_chars:
                            line = line[:max_chars - 3] + "..."
                        log_surf = font_console.render(line, True, CONSOLE_TEXT)
                        screen.blit(log_surf, (console_box.x + 8, y_offset))
                        y_offset += 18

                elif mod_id == "center":
                    screen.blit(font_small.render("НОВОСТИ И МОДПАКИ", True, GRAY_TEXT), (p_rect.x + 15, p_rect.y + 12))
                    
                    # Отрисовка вкладок внутри центрального модуля[cite: 1]
                    tab_news_rect = pygame.Rect(p_rect.x + 15, p_rect.y + 35, 90, 30)
                    tab_packs_rect = pygame.Rect(tab_news_rect.right + 8, p_rect.y + 35, 90, 30)
                    tab_browser_rect = pygame.Rect(tab_packs_rect.right + 8, p_rect.y + 35, 110, 30)

                    def draw_tab_btn(rect, title, is_active):
                        pygame.draw.rect(screen, ACCENT_COLOR if is_active else CARD_BG, rect, border_radius=6)
                        pygame.draw.rect(screen, BORDER_COLOR, rect, width=1, border_radius=6)
                        t_surf = font_small.render(title, True, TEXT_COLOR)
                        screen.blit(t_surf, (rect.centerx - t_surf.get_width()//2, rect.centery - t_surf.get_height()//2))

                    draw_tab_btn(tab_news_rect, "Новости", center_active_tab == "news")
                    draw_tab_btn(tab_packs_rect, "Модпаки", center_active_tab == "modpacks")
                    draw_tab_btn(tab_browser_rect, "Браузер модов", center_active_tab == "browser")

                    center_box = pygame.Rect(p_rect.x + 12, p_rect.y + 75, p_rect.width - 24, p_rect.height - 87)
                    pygame.draw.rect(screen, INPUT_BG, center_box, border_radius=8)
                    pygame.draw.rect(screen, BORDER_COLOR, center_box, width=1, border_radius=8)
                    
                    if center_active_tab == "news":
                        center_msg = font_subtitle.render("[ Сборки и новости загружены ]", True, TEXT_COLOR)
                        screen.blit(center_msg, (center_box.centerx - center_msg.get_width() // 2, center_box.centery - 20))
                        sub_c_msg = font_main.render("Используйте выпадающий список для выбора версии.", True, GRAY_TEXT)
                        screen.blit(sub_c_msg, (center_box.centerx - sub_c_msg.get_width() // 2, center_box.centery + 5))
                    elif center_active_tab == "modpacks":
                        center_msg = font_subtitle.render("[ Установленные модпаки ]", True, TEXT_COLOR)
                        screen.blit(center_msg, (center_box.centerx - center_msg.get_width() // 2, center_box.centery - 20))
                        sub_c_msg = font_main.render(f"Активная сборка: {cur_ver if cur_ver else 'Не выбрана'}", True, SUCCESS_COLOR)
                        screen.blit(sub_c_msg, (center_box.centerx - sub_c_msg.get_width() // 2, center_box.centery + 5))
                    elif center_active_tab == "browser":
                        # Браузер модов внутри вкладки[cite: 1]
                        search_box_rect = pygame.Rect(center_box.x + 10, center_box.y + 10, center_box.width - 125, 36)
                        filter_btn_rect = pygame.Rect(search_box_rect.right + 10, center_box.y + 10, 95, 36)

                        pygame.draw.rect(screen, CARD_BG, search_box_rect, border_radius=6)
                        pygame.draw.rect(screen, ACCENT_COLOR if mod_browser_search_active else BORDER_COLOR, search_box_rect, width=2 if mod_browser_search_active else 1, border_radius=6)
                        
                        display_search_txt = mod_browser_search_text + ("|" if mod_browser_search_active else "")
                        if not display_search_txt:
                            display_search_txt = "Введите первые буквы мода..."
                        screen.blit(font_main.render(display_search_txt, True, TEXT_COLOR if mod_browser_search_text else GRAY_TEXT), (search_box_rect.x + 10, search_box_rect.y + 10))

                        # Кнопка Фильтр[cite: 1]
                        pygame.draw.rect(screen, ACCENT_COLOR, filter_btn_rect, border_radius=6)
                        screen.blit(font_main.render("Фильтры", True, TEXT_COLOR), (filter_btn_rect.centerx - 28, filter_btn_rect.centery - 7))

                        # Список результатов поиска модов
                        results_clip_rect = pygame.Rect(center_box.x + 10, center_box.y + 55, center_box.width - 20, center_box.height - 65)
                        old_clip = screen.get_clip()
                        screen.set_clip(results_clip_rect)

                        y_off = results_clip_rect.y + 5 - mod_browser_scroll_offset
                        if not cached_mod_results:
                            empty_lbl = font_main.render("Введите запрос или нажмите Фильтры", True, GRAY_TEXT)
                            screen.blit(empty_lbl, (results_clip_rect.centerx - empty_lbl.get_width()//2, results_clip_rect.centery - 10))
                        else:
                            for idx, m_item in enumerate(cached_mod_results):
                                item_r = pygame.Rect(results_clip_rect.x, y_off + idx * 65, results_clip_rect.width - 12, 55)
                                pygame.draw.rect(screen, PANEL_BG, item_r, border_radius=6)
                                pygame.draw.rect(screen, BORDER_COLOR, item_r, width=1, border_radius=6)

                                title = m_item.get("title", "Mod")
                                desc = m_item.get("description", "No description")
                                screen.blit(font_main.render(title[:32], True, TEXT_COLOR), (item_r.x + 10, item_r.y + 8))
                                screen.blit(font_small.render(desc[:45] + "...", True, GRAY_TEXT), (item_r.x + 10, item_r.y + 28))

                                install_btn = pygame.Rect(item_r.right - 85, item_r.y + 12, 75, 30)
                                pygame.draw.rect(screen, SUCCESS_COLOR, install_btn, border_radius=6)
                                screen.blit(font_small.render("Установить", True, TEXT_COLOR), (install_btn.centerx - 28, install_btn.centery - 6))

                        screen.set_clip(old_clip)

                elif mod_id == "right":
                    screen.blit(font_small.render("3D ПЕРСОНАЖ", True, GRAY_TEXT), (p_rect.x + 15, p_rect.y + 12))

                    pygame.draw.rect(screen, INPUT_BG, skin_preview_box, border_radius=10)
                    pygame.draw.rect(screen, BORDER_COLOR, skin_preview_box, width=1, border_radius=10)

                    if skin_preview_box.height > 60:
                        skin_3d = render_full_3d_skin(skin_preview_box)
                        screen.blit(skin_3d, (skin_preview_box.x, skin_preview_box.y))

                    skin_status_text = "Стандартный скин" if not skin_path else os.path.basename(skin_path)
                    if len(skin_status_text) > 18:
                        skin_status_text = skin_status_text[:15] + "..."
                    status_surf = font_small.render(skin_status_text, True, TEXT_COLOR)
                    screen.blit(status_surf, (skin_preview_box.centerx - status_surf.get_width() // 2, skin_preview_box.bottom - 20))

                    btn_c = ACCENT_HOVER if change_skin_btn.collidepoint(mouse_pos) else ACCENT_COLOR
                    pygame.draw.rect(screen, btn_c, change_skin_btn, border_radius=8)
                    pygame.draw.rect(screen, BORDER_COLOR, change_skin_btn, width=1, border_radius=8)
                    cs_surf = font_main.render("Загрузить скин", True, TEXT_COLOR)
                    screen.blit(cs_surf, (change_skin_btn.centerx - cs_surf.get_width() // 2, change_skin_btn.centery - cs_surf.get_height() // 2))

                    pygame.draw.rect(screen, CARD_BG, reset_skin_btn, border_radius=8)
                    pygame.draw.rect(screen, BORDER_COLOR, reset_skin_btn, width=1, border_radius=8)
                    rs_surf = font_small.render("Сбросить скин", True, GRAY_TEXT)
                    screen.blit(rs_surf, (reset_skin_btn.centerx - rs_surf.get_width() // 2, reset_skin_btn.centery - rs_surf.get_height() // 2))

                if edit_layout_mode:
                    hr = resize_handle_rects[mod_id]
                    pygame.draw.rect(screen, ACCENT_COLOR, hr, border_radius=4)
                    pygame.draw.rect(screen, TEXT_COLOR, hr, width=1, border_radius=4)

            if edit_layout_mode:
                banner_rect = pygame.Rect(cur_w // 2 - 290, 20, 580, 40)
                pygame.draw.rect(screen, ACCENT_COLOR, banner_rect, border_radius=20)
                pygame.draw.rect(screen, TEXT_COLOR, banner_rect, width=2, border_radius=20)
                banner_text = font_main.render("Тяни за линии сетки (пропорции) или за углы | ESC — Готово", True, TEXT_COLOR)
                screen.blit(banner_text, (banner_rect.centerx - banner_text.get_width() // 2, banner_rect.centery - banner_text.get_height() // 2))

            pygame.draw.rect(screen, INPUT_BG, dropdown_rect, border_radius=10)
            pygame.draw.rect(screen, BORDER_COLOR, dropdown_rect, width=1, border_radius=10)

            cur_ver_text = cur_ver if cur_ver else "Нет установленных версий"
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
            draw_icon_btn(create_version_btn, "pencil")
            draw_icon_btn(edit_version_btn, "editpin") 

            btn_color = DANGER_COLOR if running_state else SUCCESS_COLOR
            if launch_btn_rect.collidepoint(mouse_pos):
                btn_color = DANGER_HOVER if running_state else (50, 180, 80)
            pygame.draw.rect(screen, btn_color, launch_btn_rect, border_radius=10)

            launch_text = "ОСТАНОВИТЬ" if running_state else "ИГРАТЬ"
            l_surf = font_title.render(launch_text, True, TEXT_COLOR)
            screen.blit(l_surf, (launch_btn_rect.centerx - l_surf.get_width() // 2, launch_btn_rect.centery - l_surf.get_height() // 2))

            if dropdown_open:
                menu_height = min(220, len(versions) * 45)
                dropdown_list_rect = pygame.Rect(dropdown_rect.x, dropdown_rect.y - menu_height - 5, dropdown_rect.width, menu_height)
                pygame.draw.rect(screen, PANEL_BG, dropdown_list_rect, border_radius=8)
                pygame.draw.rect(screen, BORDER_COLOR, dropdown_list_rect, width=1, border_radius=8)

                old_clip = screen.get_clip()
                screen.set_clip(dropdown_list_rect)

                for i, v in enumerate(versions):
                    item_y = dropdown_list_rect.y + 5 + i * 45 - versions_scroll_offset
                    if item_y + 45 > dropdown_list_rect.y and item_y < dropdown_list_rect.bottom:
                        is_sel = (i == selected_ver_idx)
                        item_r = pygame.Rect(dropdown_list_rect.x + 5, item_y, dropdown_list_rect.width - 15, 40)
                        if is_sel:
                            pygame.draw.rect(screen, ACCENT_COLOR, item_r, border_radius=6)
                        elif item_r.collidepoint(mouse_pos):
                            pygame.draw.rect(screen, CARD_BG, item_r, border_radius=6)
                        
                        screen.blit(font_main.render(v, True, TEXT_COLOR), (item_r.x + 10, item_r.centery - 7))

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
            screen.blit(font_main.render("← Назад", True, TEXT_COLOR), (mods_back_btn.x + 18, mods_back_btn.y + 9))

            pygame.draw.rect(screen, INPUT_BG, modrinth_search_rect, border_radius=8)
            pygame.draw.rect(screen, ACCENT_COLOR if modrinth_input_active else BORDER_COLOR, modrinth_search_rect, width=2 if modrinth_input_active else 1, border_radius=8)
            mod_s_txt = modrinth_input_text + ("|" if modrinth_input_active else "")
            if not mod_s_txt and not modrinth_input_active:
                mod_s_txt = "Введите Slug мода с Modrinth..."
            screen.blit(font_main.render(mod_s_txt, True, TEXT_COLOR if modrinth_input_text else GRAY_TEXT), (modrinth_search_rect.x + 12, modrinth_search_rect.y + 11))

            pygame.draw.rect(screen, SUCCESS_COLOR, modrinth_install_btn, border_radius=8)
            screen.blit(font_main.render("Установить", True, TEXT_COLOR), (modrinth_install_btn.centerx - 38, modrinth_install_btn.centery - 7))

            draw_icon_btn(mods_folder_btn, "folder")
            draw_icon_btn(mods_copy_btn, "copy")

            status_surf = font_small.render(modrinth_download_status, True, ACCENT_COLOR)
            screen.blit(status_surf, (mods_top_panel.x + 15, mods_top_panel.bottom - 22))

            pygame.draw.rect(screen, PANEL_BG, mods_list_rect, border_radius=12)
            pygame.draw.rect(screen, BORDER_COLOR, mods_list_rect, width=1, border_radius=12)

            old_clip = screen.get_clip()
            screen.set_clip(mods_list_rect)

            y_offset = mods_list_rect.y + 10 - mods_scroll_offset
            for idx, mod_file in enumerate(local_mods):
                item_rect = pygame.Rect(mods_list_rect.x + 10, y_offset, mods_list_rect.width - 30, 48)
                if item_rect.bottom > mods_list_rect.y and item_rect.y < mods_list_rect.bottom:
                    pygame.draw.rect(screen, CARD_BG, item_rect, border_radius=8)
                    pygame.draw.rect(screen, BORDER_COLOR, item_rect, width=1, border_radius=8)

                    screen.blit(font_main.render(mod_file, True, TEXT_COLOR), (item_rect.x + 15, item_rect.centery - 7))

                    del_btn = pygame.Rect(item_rect.right - 90, item_rect.y + 9, 80, 30)
                    toggle_btn = pygame.Rect(del_btn.x - 90, item_rect.y + 9, 80, 30)

                    is_disabled = mod_file.endswith(".disabled")
                    toggle_text = "Включить" if is_disabled else "Отключить"
                    toggle_color = SUCCESS_COLOR if is_disabled else (200, 140, 40)

                    pygame.draw.rect(screen, toggle_color, toggle_btn, border_radius=6)
                    screen.blit(font_small.render(toggle_text, True, TEXT_COLOR), (toggle_btn.centerx - 26, toggle_btn.centery - 6))

                    pygame.draw.rect(screen, DANGER_COLOR, del_btn, border_radius=6)
                    screen.blit(font_small.render("Удалить", True, TEXT_COLOR), (del_btn.centerx - 22, del_btn.centery - 6))

                y_offset += 55

            screen.set_clip(old_clip)

            max_mod_scroll = max(0, len(local_mods) * 55 - (mods_list_rect.height - 20))
            if max_mod_scroll > 0:
                scroll_bar_height = max(20, mods_list_rect.height * (mods_list_rect.height / (len(local_mods) * 55)))
                scroll_y = mods_list_rect.y + 5 + (mods_scroll_offset / max_mod_scroll) * (mods_list_rect.height - 10 - scroll_bar_height)
                mods_scrollbar_rect = pygame.Rect(mods_list_rect.right - 10, scroll_y, 6, scroll_bar_height)
                pygame.draw.rect(screen, ACCENT_COLOR, mods_scrollbar_rect, border_radius=3)

        elif current_page == "settings":
            pygame.draw.rect(screen, PANEL_BG, settings_sidebar_rect, border_radius=12)
            pygame.draw.rect(screen, BORDER_COLOR, settings_sidebar_rect, width=1, border_radius=12)

            pygame.draw.rect(screen, CARD_BG, settings_back_btn, border_radius=8)
            pygame.draw.rect(screen, BORDER_COLOR, settings_back_btn, width=1, border_radius=8)
            screen.blit(font_main.render("← Назад", True, TEXT_COLOR), (settings_back_btn.x + 18, settings_back_btn.y + 9))

            def draw_set_tab_btn(rect, title, is_active):
                pygame.draw.rect(screen, ACCENT_COLOR if is_active else CARD_BG, rect, border_radius=8)
                pygame.draw.rect(screen, BORDER_COLOR, rect, width=1, border_radius=8)
                screen.blit(font_main.render(title, True, TEXT_COLOR), (rect.x + 15, rect.centery - 7))

            draw_set_tab_btn(set_tab_general_btn, "Основные", settings_tab == "general")
            draw_set_tab_btn(set_tab_appearance_btn, "Внешний вид", settings_tab == "appearance")

            pygame.draw.rect(screen, PANEL_BG, settings_content_rect, border_radius=12)
            pygame.draw.rect(screen, BORDER_COLOR, settings_content_rect, width=1, border_radius=12)

            pygame.draw.rect(screen, ACCENT_COLOR, settings_apply_btn, border_radius=8)
            screen.blit(font_main.render("Применить", True, TEXT_COLOR), (settings_apply_btn.centerx - 38, settings_apply_btn.centery - 7))

            pygame.draw.rect(screen, CARD_BG, settings_cancel_btn, border_radius=8)
            screen.blit(font_main.render("Отмена", True, TEXT_COLOR), (settings_cancel_btn.centerx - 26, settings_cancel_btn.centery - 7))

            if settings_tab == "general":
                screen.blit(font_subtitle.render("Выделение оперативной памяти (RAM)", True, TEXT_COLOR), (settings_content_rect.x + 30, settings_content_rect.y + 30))
                
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

                screen.blit(font_subtitle.render("Действие при запуске игры", True, TEXT_COLOR), (settings_content_rect.x + 30, settings_content_rect.y + 210))
                pygame.draw.rect(screen, CARD_BG, action_toggle_btn, border_radius=8)
                act_label = LAUNCH_ACTION_LABELS.get(temp_launch_action, "Закрывать лаунчер")
                screen.blit(font_main.render(f"Режим: {act_label}", True, TEXT_COLOR), (action_toggle_btn.x + 15, action_toggle_btn.centery - 7))

                screen.blit(font_subtitle.render("Авто-бэкап", True, TEXT_COLOR), (settings_content_rect.x + 30, settings_content_rect.y + 285))
                pygame.draw.rect(screen, ACCENT_COLOR if temp_auto_backup_enabled else CARD_BG, auto_backup_btn, border_radius=8)
                backup_label = "ВКЛ" if temp_auto_backup_enabled else "ВЫКЛ"
                screen.blit(font_main.render(f"Авто-бэкап: {backup_label}", True, TEXT_COLOR), (auto_backup_btn.x + 15, auto_backup_btn.centery - 7))

            elif settings_tab == "appearance":
                screen.blit(font_subtitle.render("Тема оформления", True, TEXT_COLOR), (settings_content_rect.x + 30, settings_content_rect.y + 30))
                
                is_dark = (temp_theme == "dark")
                pygame.draw.rect(screen, ACCENT_COLOR if is_dark else CARD_BG, theme_dark_btn, border_radius=8)
                screen.blit(font_main.render("Темная", True, TEXT_COLOR), (theme_dark_btn.centerx - 24, theme_dark_btn.centery - 7))

                pygame.draw.rect(screen, ACCENT_COLOR if not is_dark else CARD_BG, theme_light_btn, border_radius=8)
                screen.blit(font_main.render("Светлая", True, TEXT_COLOR), (theme_light_btn.centerx - 26, theme_light_btn.centery - 7))

                screen.blit(font_subtitle.render("Акцентный цвет интерфейса", True, TEXT_COLOR), (settings_content_rect.x + 30, settings_content_rect.y + 150))
                for idx, col in enumerate(DEFAULT_PRESETS):
                    c_rect = pygame.Rect(settings_content_rect.x + 30 + idx * 50, settings_content_rect.y + 180, 36, 36)
                    pygame.draw.rect(screen, col, c_rect, border_radius=18)
                    if temp_accent_idx == idx:
                        pygame.draw.rect(screen, TEXT_COLOR, c_rect, width=2, border_radius=18)

                custom_btn_rect = pygame.Rect(settings_content_rect.x + 30 + len(DEFAULT_PRESETS) * 50, settings_content_rect.y + 180, 36, 36)
                pygame.draw.rect(screen, temp_custom_color, custom_btn_rect, border_radius=18)
                screen.blit(font_small.render("🎨", True, TEXT_COLOR), (custom_btn_rect.centerx - 7, custom_btn_rect.centery - 7))


                screen.blit(font_subtitle.render("Фон модулей", True, TEXT_COLOR), (settings_content_rect.x + 30, settings_content_rect.y + 225))
                pygame.draw.rect(screen, ACCENT_COLOR if temp_bg_mode == "none" else CARD_BG, bg_none_btn, border_radius=8)
                screen.blit(font_main.render("Без фона", True, TEXT_COLOR), (bg_none_btn.centerx - 30, bg_none_btn.centery - 7))

                pygame.draw.rect(screen, ACCENT_COLOR if temp_bg_mode == "custom" else CARD_BG, bg_custom_btn, border_radius=8)
                screen.blit(font_main.render("Свой файл...", True, TEXT_COLOR), (bg_custom_btn.centerx - 38, bg_custom_btn.centery - 7))

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
                    font_small.render("ЦВЕТ УЗОРА ФОНА", True, GRAY_TEXT),
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
                    pygame.draw.rect(screen, PANEL_BG, bg_picker_rect, border_radius=10)
                    pygame.draw.rect(screen, BORDER_COLOR, bg_picker_rect, width=1, border_radius=10)
                    if picker_surface:
                        screen.blit(picker_surface, (bg_picker_rect.x + 10, bg_picker_rect.y + 10))

                # --- Кнопка редагування сітки ---
                # Теж опускаємо нижче, щоб вона не зливалася з пікером
                toggle_edit_layout_btn.y = settings_content_rect.y + 430 + (PICKER_SIZE if bg_color_picker_open else 0)

                pygame.draw.rect(screen, CARD_BG, toggle_edit_layout_btn, border_radius=8)
                pygame.draw.rect(screen, BORDER_COLOR, toggle_edit_layout_btn, width=1, border_radius=8)
                screen.blit(
                    font_main.render("Редактировать сетку модулей", True, TEXT_COLOR),
                    (toggle_edit_layout_btn.x + 15, toggle_edit_layout_btn.y + 12)
                )
                pygame.draw.rect(screen, ACCENT_COLOR, toggle_edit_layout_btn, border_radius=8)
                screen.blit(font_main.render("⚙ Редактировать сетку модулей", True, TEXT_COLOR), (toggle_edit_layout_btn.centerx - 110, toggle_edit_layout_btn.centery - 7))
                if color_picker_open:
                    screen.blit(picker_surface, (picker_rect.x + 10, picker_rect.y + 10))
                    pygame.draw.rect(screen, TEXT_COLOR, picker_rect, width=1, border_radius=6)
        pygame.display.flip()
        clock.tick(60)