import sys
import os
import re
import json
import time
import shutil
import threading
import subprocess
from pathlib import Path
from datetime import datetime

import pygame

WINDOW_TITLE = "Mace Doctor"
NORMAL_SIZE = (620, 430)
DETAILS_SIZE = (900, 650)

BG = (11, 13, 16)
SURFACE = (17, 21, 26)
CARD = (24, 29, 35)
CARD_HOVER = (29, 36, 44)
BLUE = (59, 130, 246)
BLUE_LIGHT = (96, 165, 250)
TEXT = (244, 247, 250)
SECONDARY = (154, 164, 178)
SUCCESS = (74, 222, 128)
ERROR = (248, 113, 113)
WARNING = (250, 204, 21)
BORDER = (38, 45, 54)

USER_AGENT = "MaceDoctor/1.0"


def console(message):
    print(f"[Mace Doctor {datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def normalize_path(path):
    return os.path.abspath(os.path.expanduser(path))


def find_latest_log(instance_dir):
    candidates = []
    logs_dir = Path(instance_dir) / "logs"
    crash_dir = Path(instance_dir) / "crash-reports"

    latest = logs_dir / "latest.log"
    if latest.exists():
        candidates.append(latest)

    if logs_dir.exists():
        candidates.extend(logs_dir.glob("*.log"))

    if crash_dir.exists():
        candidates.extend(crash_dir.glob("*.txt"))

    candidates = [p for p in candidates if p.is_file()]
    if not candidates:
        return None

    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_text_file(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        console(f"Не удалось прочитать {path}: {exc}")
        return ""


class LogAnalyzer:
    PATTERNS = {
        "OutOfMemory": [
            "OutOfMemoryError",
            "Java heap space",
            "GC overhead limit exceeded",
        ],
        "ModCrash": [
            "Mixin",
            "ModLoadingException",
            "ModLoading",
            "Exception in mod",
            "Failed to load mod",
            "Error loading mod",
        ],
        "JavaCrash": [
            "Exception in thread",
            "java.lang.",
            "Caused by:",
        ],
        "Rendering": [
            "OpenGL",
            "GLFW",
            "RenderSystem",
            "graphics",
            "renderer",
        ],
        "MissingDependency": [
            "requires",
            "dependency",
            "missing dependency",
            "depends on",
        ],
        "VersionError": [
            "UnsupportedClassVersionError",
            "incompatible",
            "wrong version",
            "Unsupported version",
        ],
    }

    MOD_PATTERN = re.compile(
        r"(?:mod|modid|mod_id)[\s:=]+([a-zA-Z0-9_.\-]+)",
        re.IGNORECASE,
    )

    def analyze(self, text):
        if not text:
            return {
                "type": "Unknown",
                "short": "Не удалось найти лог Minecraft.",
                "details": "Mace Doctor не смог найти подходящий лог для анализа.",
                "suspected_mod": None,
                "confidence": 0,
                "errors": [],
            }

        found = []
        for category, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in text.lower():
                    found.append((category, pattern))

        suspected_mod = None
        matches = self.MOD_PATTERN.findall(text)
        if matches:
            suspected_mod = matches[-1]

        if any(x[0] == "OutOfMemory" for x in found):
            result_type = "OutOfMemory"
            short = "Minecraftу не хватило оперативной памяти."
        elif any(x[0] == "MissingDependency" for x in found):
            result_type = "MissingDependency"
            short = "Обнаружена проблема с зависимостью мода."
        elif any(x[0] == "VersionError" for x in found):
            result_type = "VersionError"
            short = "Обнаружена несовместимость версии."
        elif any(x[0] == "ModCrash" for x in found):
            result_type = "ModCrash"
            short = "Похоже, ошибка связана с модом."
        elif any(x[0] == "Rendering" for x in found):
            result_type = "Rendering"
            short = "Обнаружена проблема с графикой или рендерингом."
        elif any(x[0] == "JavaCrash" for x in found):
            result_type = "JavaCrash"
            short = "Minecraft завершился из-за ошибки Java."
        else:
            result_type = "Unknown"
            short = "Mace Doctor не смог точно определить причину."

        details_lines = []
        for category, pattern in found[:12]:
            details_lines.append(f"{category}: найдено «{pattern}»")

        if suspected_mod:
            details_lines.append(f"Предполагаемый мод: {suspected_mod}")

        if not details_lines:
            details_lines.append("В логе не найдено характерных признаков ошибки.")

        confidence = min(95, 35 + len(found) * 10)

        return {
            "type": result_type,
            "short": short,
            "details": "\n".join(details_lines),
            "suspected_mod": suspected_mod,
            "confidence": confidence,
            "errors": found,
        }


class ModManager:
    def __init__(self, instance_dir):
        self.instance_dir = Path(instance_dir)
        self.mods_dir = self.instance_dir / "mods"
        self.disabled_dir = None

    def disable_mods(self):
        if not self.mods_dir.exists():
            console("Папка mods не найдена.")
            return None

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.disabled_dir = self.instance_dir / f"mods_disabled_{stamp}"

        console(f"Перемещаю mods -> {self.disabled_dir.name}")
        self.mods_dir.rename(self.disabled_dir)
        self.mods_dir.mkdir(parents=True, exist_ok=True)
        return self.disabled_dir

    def restore_mods(self):
        if not self.disabled_dir or not self.disabled_dir.exists():
            console("Резервная папка модов не найдена.")
            return False

        if self.mods_dir.exists():
            shutil.rmtree(self.mods_dir)

        console(f"Восстанавливаю {self.disabled_dir.name} -> mods")
        self.disabled_dir.rename(self.mods_dir)
        return True

    def find_latest_backup(self):
        backups = list(self.instance_dir.glob("mods_disabled_*"))
        backups = [p for p in backups if p.is_dir()]
        if not backups:
            return None
        return max(backups, key=lambda p: p.stat().st_mtime)


class BuildInspector:
    def __init__(self, instance_dir):
        self.instance_dir = Path(instance_dir)

    def inspect_mods(self):
        mods_dir = self.instance_dir / "mods"
        result = []

        if not mods_dir.exists():
            console("mods отсутствует.")
            return result

        for file in mods_dir.iterdir():
            if file.suffix.lower() in (".jar", ".zip"):
                result.append(file.name)

        console(f"Найдено модов: {len(result)}")
        return result

    def inspect_configs(self):
        config_dir = self.instance_dir / "config"
        result = []

        if not config_dir.exists():
            console("config отсутствует.")
            return result

        for file in config_dir.rglob("*.json"):
            result.append(file)

        console(f"JSON-конфигураций: {len(result)}")
        return result

    def inspect_versions(self):
        versions_dir = self.instance_dir / "versions"
        result = []

        if not versions_dir.exists():
            console("versions отсутствует.")
            return result

        for file in versions_dir.rglob("*.json"):
            result.append(file)

        console(f"Файлов версий: {len(result)}")
        return result


class ConfigChecker:
    def __init__(self, instance_dir):
        self.instance_dir = Path(instance_dir)

    def check(self):
        config_dir = self.instance_dir / "config"
        errors = []

        if not config_dir.exists():
            return errors

        for file in config_dir.rglob("*.json"):
            try:
                json.loads(file.read_text(encoding="utf-8", errors="ignore"))
            except Exception as exc:
                errors.append((str(file), str(exc)))
                console(f"Ошибка JSON: {file}")

        return errors


class VersionChecker:
    def __init__(self, instance_dir):
        self.instance_dir = Path(instance_dir)

    def check(self):
        versions_dir = self.instance_dir / "versions"
        errors = []

        if not versions_dir.exists():
            return errors

        for file in versions_dir.rglob("*.json"):
            try:
                json.loads(file.read_text(encoding="utf-8", errors="ignore"))
            except Exception as exc:
                errors.append((str(file), str(exc)))
                console(f"Ошибка JSON версии: {file}")

        return errors


class MinecraftTester:
    def __init__(self, instance_dir, launch_command=None):
        self.instance_dir = Path(instance_dir)
        self.launch_command = launch_command

    def test(self):
        if not self.launch_command:
            console("Команда запуска не задана. Тестовый запуск пропущен.")
            return True

        console("Запускаю Minecraft без GUI для проверки.")

        try:
            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW

            process = subprocess.Popen(
                self.launch_command,
                cwd=str(self.instance_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
                shell=isinstance(self.launch_command, str),
            )

            start = time.time()
            while time.time() - start < 30:
                result = process.poll()
                if result is not None:
                    console(f"Minecraft завершился с кодом {result}.")
                    return result == 0
                time.sleep(0.5)

            console("Minecraft продолжает работать после тестовых 30 секунд.")
            return True
        except Exception as exc:
            console(f"Ошибка тестового запуска: {exc}")
            return False


class MaceDoctor:
    def __init__(self, instance_dir, launch_command=None):
        self.instance_dir = normalize_path(instance_dir)
        self.launch_command = launch_command
        self.analyzer = LogAnalyzer()
        self.mod_manager = ModManager(self.instance_dir)
        self.inspector = BuildInspector(self.instance_dir)
        self.config_checker = ConfigChecker(self.instance_dir)
        self.version_checker = VersionChecker(self.instance_dir)
        self.tester = MinecraftTester(self.instance_dir, launch_command)

    def analyze(self):
        log = find_latest_log(self.instance_dir)

        if log:
            console(f"Анализирую: {log}")
            text = read_text_file(log)
        else:
            console("Лог Minecraft не найден.")
            text = ""

        result = self.analyzer.analyze(text)
        result["log"] = str(log) if log else None
        return result

    def repair(self, update_status=None):
        def status(message):
            console(message)
            if update_status:
                update_status(message)

        status("Проверяю сборку...")
        self.inspector.inspect_mods()

        status("Проверяю настройки...")
        config_errors = self.config_checker.check()

        status("Проверяю файл версии...")
        version_errors = self.version_checker.check()

        status("Отключаю моды...")
        self.mod_manager.disable_mods()

        status("Проверяю запуск без модов...")
        clean_launch = self.tester.test()

        status("Восстанавливаю моды...")
        self.mod_manager.restore_mods()

        if config_errors:
            status(f"Найдено ошибок конфигурации: {len(config_errors)}")

        if version_errors:
            status(f"Найдено ошибок версии: {len(version_errors)}")

        if clean_launch:
            status("Запуск без модов прошёл успешно.")
            return True

        status("Тестовый запуск завершился ошибкой.")
        return False


class Button:
    def __init__(self, rect, text, callback=None, primary=False):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.callback = callback
        self.primary = primary
        self.enabled = True
        self.hovered = False

    def update(self, mouse_pos):
        self.hovered = self.enabled and self.rect.collidepoint(mouse_pos)

    def click(self):
        if self.enabled and self.callback:
            self.callback()

    def draw(self, screen, font):
        if self.primary:
            color = BLUE_LIGHT if self.hovered else BLUE
            border = color
        else:
            color = CARD_HOVER if self.hovered else CARD
            border = BLUE if self.hovered else BORDER

        pygame.draw.rect(screen, color, self.rect, border_radius=10)
        if not self.primary:
            pygame.draw.rect(screen, border, self.rect, width=1, border_radius=10)

        label = font.render(self.text, True, TEXT)
        screen.blit(label, label.get_rect(center=self.rect.center))


class Spinner:
    def __init__(self):
        self.angle = 0

    def update(self):
        self.angle = (self.angle + 7) % 360

    def draw(self, screen, center, radius=20):
        rect = pygame.Rect(0, 0, radius * 2, radius * 2)
        rect.center = center
        start = pygame.math.Vector2(center)
        pygame.draw.arc(screen, BORDER, rect, 0, 6.0, 4)
        pygame.draw.arc(
            screen,
            BLUE,
            rect,
            pygame.math.Vector2(1, 0).angle_to(
                pygame.math.Vector2(1, 0).rotate(-self.angle)
            ) * 3.14159 / 180,
            2.2,
            4,
        )


class MaceDoctorWindow:
    def __init__(self, doctor):
        pygame.init()
        self.doctor = doctor
        self.screen = pygame.display.set_mode(NORMAL_SIZE, pygame.RESIZABLE)
        pygame.display.set_caption(WINDOW_TITLE)

        self.font = pygame.font.SysFont("Segoe UI", 17)
        self.font_small = pygame.font.SysFont("Segoe UI", 14)
        self.font_title = pygame.font.SysFont("Segoe UI", 27, bold=True)
        self.font_big = pygame.font.SysFont("Segoe UI", 20, bold=True)

        self.clock = pygame.time.Clock()
        self.running = True
        self.details = False
        self.repairing = False
        self.repair_done = False
        self.repair_success = False
        self.status_lines = []
        self.spinner = Spinner()

        self.result = self.doctor.analyze()

        self.details_button = None
        self.repair_button = None
        self.cancel_button = None

    def resize(self, expanded):
        size = DETAILS_SIZE if expanded else NORMAL_SIZE
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)

    def toggle_details(self):
        self.details = not self.details
        self.resize(self.details)

    def start_repair(self):
        if self.repairing:
            return

        self.repairing = True
        self.repair_done = False
        self.repair_success = False
        self.status_lines = ["Подготовка к исправлению..."]

        def worker():
            try:
                success = self.doctor.repair(self.set_status)
                self.repair_success = success
            except Exception as exc:
                console(f"Ошибка ремонта: {exc}")
                self.set_status("Произошла ошибка во время исправления.")
                self.repair_success = False
            finally:
                self.repair_done = True

        threading.Thread(target=worker, daemon=True).start()

    def set_status(self, message):
        self.status_lines.append(message)
        self.status_lines = self.status_lines[-4:]

    def wrap_text(self, text, font, width):
        words = text.split()
        lines = []
        current = ""

        for word in words:
            test = word if not current else current + " " + word
            if font.size(test)[0] <= width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word

        if current:
            lines.append(current)

        return lines

    def draw_header(self):
        width = self.screen.get_width()
        pygame.draw.rect(self.screen, SURFACE, (0, 0, width, 76))

        brand = self.font_small.render("MACE DOCTOR", True, BLUE_LIGHT)
        self.screen.blit(brand, (28, 18))

        title = self.font_title.render("Диагностика Minecraft", True, TEXT)
        self.screen.blit(title, (28, 39))

        pygame.draw.line(self.screen, BORDER, (28, 75), (width - 28, 75), 1)

    def draw_status_badge(self):
        if self.repairing:
            label = "ИСПРАВЛЕНИЕ"
            color = BLUE
        elif self.result["type"] == "Unknown":
            label = "ТРЕБУЕТСЯ АНАЛИЗ"
            color = WARNING
        else:
            label = "НАЙДЕНА ОШИБКА"
            color = ERROR

        text = self.font_small.render(label, True, color)
        rect = pygame.Rect(28, 94, text.get_width() + 24, 30)
        pygame.draw.rect(self.screen, CARD, rect, border_radius=8)
        pygame.draw.rect(self.screen, color, rect, width=1, border_radius=8)
        self.screen.blit(text, (rect.x + 12, rect.y + 6))

    def draw_diagnosis(self):
        width = self.screen.get_width()
        card_rect = pygame.Rect(28, 140, width - 56, 132 if not self.details else 145)
        pygame.draw.rect(self.screen, CARD, card_rect, border_radius=14)

        title = self.font_big.render("Что произошло?", True, TEXT)
        self.screen.blit(title, (card_rect.x + 20, card_rect.y + 18))

        lines = self.wrap_text(
            self.result["short"],
            self.font,
            card_rect.width - 40,
        )

        y = card_rect.y + 55
        for line in lines[:3]:
            self.screen.blit(self.font.render(line, True, SECONDARY), (card_rect.x + 20, y))
            y += 24

        if self.result.get("suspected_mod"):
            mod_text = self.font_small.render(
                f"Подозрение: {self.result['suspected_mod']}",
                True,
                WARNING,
            )
            self.screen.blit(mod_text, (card_rect.x + 20, card_rect.bottom - 27))

    def draw_details(self):
        if not self.details:
            return

        width = self.screen.get_width()
        panel = pygame.Rect(28, 300, width - 56, 260)
        pygame.draw.rect(self.screen, SURFACE, panel, border_radius=14)
        pygame.draw.rect(self.screen, BORDER, panel, width=1, border_radius=14)

        title = self.font_big.render("Подробный анализ", True, BLUE_LIGHT)
        self.screen.blit(title, (panel.x + 20, panel.y + 18))

        y = panel.y + 58
        lines = self.result["details"].splitlines()

        for source_line in lines:
            wrapped = self.wrap_text(
                source_line,
                self.font_small,
                panel.width - 40,
            )
            for line in wrapped:
                if y > panel.bottom - 32:
                    break
                self.screen.blit(
                    self.font_small.render(line, True, SECONDARY),
                    (panel.x + 20, y),
                )
                y += 21

    def draw_repair_state(self):
        width = self.screen.get_width()
        height = self.screen.get_height()

        center = (width // 2, 285 if self.details else 250)
        self.spinner.update()
        self.spinner.draw(self.screen, center, 22)

        title = self.font_big.render(
            "Mace Doctor исправляет проблему...",
            True,
            TEXT,
        )
        self.screen.blit(title, title.get_rect(center=(center[0], center[1] + 42)))

        y = height - 105
        for line in self.status_lines[-3:]:
            text = self.font_small.render(line, True, SECONDARY)
            self.screen.blit(text, (28, y))
            y += 22

    def draw_buttons(self):
        width = self.screen.get_width()
        height = self.screen.get_height()

        if self.repairing:
            return

        button_y = height - 58

        self.details_button = Button(
            (28, button_y, 130, 40),
            "Скрыть" if self.details else "Подробнее",
            self.toggle_details,
        )

        self.cancel_button = Button(
            (width - 250, button_y, 105, 40),
            "Отменить",
            self.stop,
        )

        self.repair_button = Button(
            (width - 135, button_y, 107, 40),
            "Исправить",
            self.start_repair,
            primary=True,
        )

        mouse = pygame.mouse.get_pos()
        for button in (self.details_button, self.cancel_button, self.repair_button):
            button.update(mouse)
            button.draw(self.screen, self.font_small)

    def draw(self):
        self.screen.fill(BG)
        self.draw_header()

        if self.repairing:
            self.draw_repair_state()
        else:
            self.draw_status_badge()
            self.draw_diagnosis()
            self.draw_details()
            self.draw_buttons()

        if self.repair_done and not self.repairing:
            result_text = (
                "Исправление завершено"
                if self.repair_success
                else "Не удалось автоматически исправить проблему"
            )
            color = SUCCESS if self.repair_success else ERROR
            text = self.font_small.render(result_text, True, color)
            self.screen.blit(text, (28, self.screen.get_height() - 88))

    def stop(self):
        self.running = False

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                elif event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode(
                        (max(520, event.w), max(360, event.h)),
                        pygame.RESIZABLE,
                    )

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.repairing:
                        continue

                    mouse = event.pos
                    for button in (
                        self.details_button,
                        self.cancel_button,
                        self.repair_button,
                    ):
                        if button and button.rect.collidepoint(mouse):
                            button.click()
                            break

            self.draw()
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()


def parse_args():
    instance = None
    launch_command = None

    args = sys.argv[1:]
    i = 0

    while i < len(args):
        arg = args[i]

        if arg == "--launch-command" and i + 1 < len(args):
            launch_command = args[i + 1]
            i += 2
            continue

        if not arg.startswith("-") and instance is None:
            instance = arg

        i += 1

    if instance is None:
        instance = os.getcwd()

    return normalize_path(instance), launch_command


def main():
    instance_dir, launch_command = parse_args()

    console(f"Instance: {instance_dir}")
    console("Mace Doctor запущен.")

    doctor = MaceDoctor(instance_dir, launch_command)
    window = MaceDoctorWindow(doctor)
    window.run()


if __name__ == "__main__":
    main()