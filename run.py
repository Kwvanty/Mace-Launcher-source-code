import os
import sys
import json
import subprocess

# =========================================================
# ПУТИ MACE LAUNCHER
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Добавляем корень Mace Launcher в путь поиска модулей
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# =========================================================
# БИБЛИОТЕКИ
# =========================================================

import pygame

# =========================================================
# ФАЙЛЫ
# =========================================================

FONT_PATH = os.path.join(
    BASE_DIR,
    "fonts",
    "Inter-Regular.ttf"
)

FONT_BOLD_PATH = os.path.join(
    BASE_DIR,
    "fonts",
    "Inter-SemiBold.ttf"
)

RULES_FILE = os.path.join(
    BASE_DIR,
    "treams of politics.txt"
)

ACCEPT_FILE = os.path.join(
    BASE_DIR,
    "rules_accepted.json"
)


# =========================================================
# ШРИФТЫ
# =========================================================

def load_font(path, size):
    if os.path.exists(path):
        return pygame.font.Font(path, size)

    fallback = (
        pygame.font.match_font("segoeui")
        or pygame.font.match_font("arial")
    )

    if fallback:
        return pygame.font.Font(fallback, size)

    return pygame.font.Font(None, size)


# =========================================================
# ИКОНКА
# =========================================================

def apply_window_icon():
    for icon_path in [
        os.path.join(BASE_DIR, "MaceLauncherLogo.ico"),
        os.path.join(BASE_DIR, "MaceLauncherLogo.png"),
        os.path.join(BASE_DIR, "iconMace.ico"),
    ]:

        if not os.path.exists(icon_path):
            continue

        try:
            icon_surface = pygame.image.load(icon_path)

            if icon_surface:
                pygame.display.set_icon(icon_surface)
                return True

        except Exception:
            continue

    return False


# =========================================================
# УСЛОВИЯ
# =========================================================

def read_rules():
    if not os.path.exists(RULES_FILE):
        return "Файл с условиями использования не найден."

    try:
        with open(
            RULES_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return f.read()

    except Exception:
        return "Не удалось прочитать условия использования."


def rules_accepted():
    if not os.path.exists(ACCEPT_FILE):
        return False

    try:
        with open(
            ACCEPT_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        return data.get(
            "accepted",
            False
        ) is True

    except Exception:
        return False


def save_acceptance():
    try:
        with open(
            ACCEPT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                {
                    "accepted": True
                },
                f,
                indent=4,
                ensure_ascii=False
            )

        return True

    except Exception:
        return False


# =========================================================
# ПЕРЕНОС ТЕКСТА
# =========================================================

def wrap_text(text, font, width):
    lines = []

    for paragraph in text.splitlines():

        if not paragraph.strip():
            lines.append("")
            continue

        words = paragraph.split()
        line = ""

        for word in words:

            test = (
                word
                if not line
                else line + " " + word
            )

            if font.size(test)[0] <= width:
                line = test

            else:

                if line:
                    lines.append(line)

                line = word

        if line:
            lines.append(line)

    return lines


# =========================================================
# ОКНО УСЛОВИЙ
# =========================================================

def show_rules_window():

    pygame.init()

    WIDTH, HEIGHT = 600, 450

    screen = pygame.display.set_mode(
        (
            WIDTH,
            HEIGHT
        ),
        pygame.HWSURFACE | pygame.DOUBLEBUF
    )

    apply_window_icon()

    pygame.display.set_caption(
        "Mace Launcher - Условия использования"
    )

    clock = pygame.time.Clock()

    BG = (25, 25, 30)
    BLUE = (0, 102, 204)
    TEXT = (220, 220, 220)
    WHITE = (245, 245, 245)

    ACC = (0, 120, 255)
    ACC_HOVER = (40, 150, 255)

    SCROLL_BG = (45, 45, 50)
    SCROLL = (100, 100, 105)
    SCROLL_HOVER = (140, 140, 145)

    title_font = load_font(
        FONT_BOLD_PATH,
        24
    )

    text_font = load_font(
        FONT_PATH,
        18
    )

    button_font = load_font(
        FONT_BOLD_PATH,
        17
    )

    rules = read_rules()

    text_x = 35
    text_y = 80

    line_height = 28

    button_width = 250
    button_height = 45

    button_y = HEIGHT - 65

    scrollbar_x = WIDTH - 43

    content_width = (
        scrollbar_x -
        text_x -
        12
    )

    text_bottom = button_y - 20

    viewport_height = (
        text_bottom -
        text_y
    )

    lines = wrap_text(
        rules,
        text_font,
        content_width
    )

    content_height = (
        len(lines) *
        line_height
    )

    max_scroll = max(
        0,
        content_height -
        viewport_height
    )

    scroll = 0
    dragging = False
    drag_offset = 0

    accepted = False
    running = True

    accept_rect = pygame.Rect(
        WIDTH // 2 -
        button_width // 2,

        button_y,

        button_width,
        button_height
    )

    while running:

        mouse = pygame.mouse.get_pos()

        for event in pygame.event.get():

            if event.type == pygame.QUIT:

                running = False

            elif event.type == pygame.MOUSEWHEEL:

                scroll -= event.y * 40

                scroll = max(
                    0,
                    min(
                        scroll,
                        max_scroll
                    )
                )

            elif (
                event.type ==
                pygame.MOUSEBUTTONDOWN
                and event.button == 1
            ):

                if accept_rect.collidepoint(
                    event.pos
                ):

                    if scroll >= max_scroll - 2:

                        accepted = True
                        running = False

                elif max_scroll > 0:

                    handle_h = max(
                        35,
                        int(
                            viewport_height *
                            viewport_height /
                            content_height
                        )
                    )

                    track_h = max(
                        1,
                        viewport_height -
                        handle_h
                    )

                    handle_y = (
                        text_y +
                        (
                            scroll /
                            max_scroll
                        ) *
                        track_h
                    )

                    handle = pygame.Rect(
                        scrollbar_x,
                        int(handle_y),
                        8,
                        handle_h
                    )

                    if handle.collidepoint(
                        event.pos
                    ):

                        dragging = True

                        drag_offset = (
                            event.pos[1] -
                            handle.y
                        )

            elif (
                event.type ==
                pygame.MOUSEBUTTONUP
                and event.button == 1
            ):

                dragging = False

            elif (
                event.type ==
                pygame.MOUSEMOTION
                and dragging
                and max_scroll > 0
            ):

                handle_h = max(
                    35,
                    int(
                        viewport_height *
                        viewport_height /
                        content_height
                    )
                )

                track_h = max(
                    1,
                    viewport_height -
                    handle_h
                )

                new_y = (
                    event.pos[1] -
                    drag_offset
                )

                new_y = max(
                    text_y,
                    min(
                        new_y,
                        text_y + track_h
                    )
                )

                scroll = (
                    (
                        new_y -
                        text_y
                    ) /
                    track_h
                ) * max_scroll

        screen.fill(BG)

        pygame.draw.rect(
            screen,
            BLUE,
            (0, 0, WIDTH, 10)
        )

        title = title_font.render(
            "Добро пожаловать в Mace Launcher!",
            True,
            WHITE
        )

        screen.blit(
            title,
            (35, 25)
        )

        pygame.draw.line(
            screen,
            (50, 50, 55),
            (35, 60),
            (WIDTH - 35, 60),
            1
        )

        text_area = pygame.Rect(
            text_x,
            text_y,
            content_width,
            viewport_height
        )

        screen.set_clip(text_area)

        y = text_y - scroll

        for line in lines:

            if line:

                surface = text_font.render(
                    line,
                    True,
                    TEXT
                )

                screen.blit(
                    surface,
                    (text_x, y)
                )

            y += line_height

        screen.set_clip(None)

        if max_scroll > 0:

            pygame.draw.rect(
                screen,
                SCROLL_BG,
                (
                    scrollbar_x,
                    text_y,
                    8,
                    viewport_height
                ),
                border_radius=4
            )

            handle_h = max(
                35,
                int(
                    viewport_height *
                    viewport_height /
                    content_height
                )
            )

            track_h = (
                viewport_height -
                handle_h
            )

            handle_y = (
                text_y +
                (
                    scroll /
                    max_scroll
                ) *
                track_h
            )

            handle = pygame.Rect(
                scrollbar_x,
                int(handle_y),
                8,
                handle_h
            )

            color = (
                SCROLL_HOVER
                if (
                    handle.collidepoint(mouse)
                    or dragging
                )
                else SCROLL
            )

            pygame.draw.rect(
                screen,
                color,
                handle,
                border_radius=4
            )

        button_enabled = (
            scroll >= max_scroll - 2
        )

        if button_enabled:

            color = (
                ACC_HOVER
                if accept_rect.collidepoint(mouse)
                else ACC
            )

        else:

            color = (
                55,
                55,
                60
            )

        pygame.draw.rect(
            screen,
            color,
            accept_rect,
            border_radius=7
        )

        accept_text = button_font.render(
            "Я принимаю соглашение",
            True,
            WHITE
        )

        screen.blit(
            accept_text,
            accept_text.get_rect(
                center=accept_rect.center
            )
        )

        pygame.display.flip()

        clock.tick(60)

    pygame.quit()

    return accepted


# =========================================================
# ЗАПУСК UPDATE / GUI
# =========================================================

def start_update():

    update_file = os.path.join(
        BASE_DIR,
        "update_logic.py"
    )

    if os.path.exists(update_file):

        subprocess.Popen(
            [
                sys.executable,
                update_file
            ],
            cwd=BASE_DIR
        )


# =========================================================
# MAIN
# =========================================================

def main():

    if not rules_accepted():

        if not show_rules_window():
            sys.exit()

        if not save_acceptance():
            sys.exit()

    start_update()


if __name__ == "__main__":
    main()
