#!/usr/bin/env bash
# Запуск GOR Launcher на Linux.
#   ./run_linux.sh              - обычный запуск
#   ./run_linux.sh --bigpicture - сразу в режиме Big Picture
# Первый запуск сам создаёт .venv и ставит зависимости.
set -e
cd "$(dirname "$(readlink -f "$0")")"

if [ ! -x .venv/bin/python3 ]; then
    echo "[GOR] Первый запуск: создаю виртуальное окружение..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip >/dev/null
    .venv/bin/pip install -r requirements.txt
fi

# Chromium (QtWebEngine) не стартует от root без этого флага
if [ "$(id -u)" = "0" ]; then
    export QTWEBENGINE_CHROMIUM_FLAGS="${QTWEBENGINE_CHROMIUM_FLAGS} --no-sandbox"
fi
# Wayland без xcb-плагина: пусть Qt сам выберет, но разрешим оба
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-}"
[ -z "$QT_QPA_PLATFORM" ] && unset QT_QPA_PLATFORM

exec .venv/bin/python3 bridge_loader.py "$@"
