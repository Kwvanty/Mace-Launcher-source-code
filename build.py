import shutil
import subprocess
import sys
from pathlib import Path

# Базовая директория проекта
BASE_DIR = Path(__file__).resolve().parent

print("=== Чистая сборка MaceLauncher без консоли ===")

# Определяем, какой Python использовать
embedded_python = BASE_DIR / "python" / "python.exe"
python_executable = str(embedded_python) if embedded_python.exists() else sys.executable

try:
    # 1. Очищаем старые папки кэша PyInstaller, чтобы не тянуть старые баги
    for folder_name in ["build", "dist"]:
        folder_path = BASE_DIR / folder_name
        if folder_path.exists():
            shutil.rmtree(folder_path, ignore_errors=True)
            print(f"Очищена старая папка: {folder_name}")

    # 2. Удаляем старый .exe в корне, если он заблокирован или старый
    target_exe = BASE_DIR / "MaceLauncher.exe"
    if target_exe.exists():
        try:
            target_exe.unlink()
            print("Старый MaceLauncher.exe удален.")
        except Exception:
            print("⚠️ Не удалось удалить старый MaceLauncher.exe (возможно, он сейчас запущен). Закрой его!")

    # 3. Собираем заново с жестким флагом --noconsole
    command = [
        python_executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--noconsole",
        "--icon=iconMace.ico",
        "--name=MaceLauncher",
        "--clean",
        "launcher.py"
    ]

    print("\nИдет сборка... Пожалуйста, подожди пару секунд.")
    subprocess.run(command, cwd=str(BASE_DIR), check=True)

    # 4. Переносим свежий .exe в корень
    dist_exe = BASE_DIR / "dist" / "MaceLauncher.exe"
    if dist_exe.exists():
        shutil.copy2(dist_exe, target_exe)
        print("\n✅ Успех! Новый MaceLauncher.exe собран и скопирован в корень. Консоли больше не будет!")
    else:
        print("\n⚠️ Ошибка: файл в dist не найден.")

except Exception as e:
    print(f"\n❌ Ошибка во время сборки: {e}")

input("\nНажми Enter для выхода...")