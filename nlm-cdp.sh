#!/bin/bash
# nlm CDP 模式 - Mac 版
# 所有 nlm 调用都连接到同一个 Chrome，避免 Profile 冲突

CDP_PORT=9333
CDP_URL="http://127.0.0.1:$CDP_PORT"
CHROME_PROFILE="$HOME/.claude/skills/notebooklm/chrome_profile"
REAL_NLM="$(which nlm)"

# 检查 Chrome CDP 是否在运行
check_cdp() {
    curl -s "$CDP_URL/json/version" > /dev/null 2>&1
}

# 启动 Chrome CDP
start_chrome() {
    # 清理残留文件
    rm -f "$CHROME_PROFILE/SingletonLock" "$CHROME_PROFILE/SingletonSocket" "$CHROME_PROFILE/SingletonCookie" 2>/dev/null

    echo "🚀 启动 Chrome CDP (端口 $CDP_PORT)..."

    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
        --remote-debugging-port=$CDP_PORT \
        --user-data-dir="$CHROME_PROFILE" \
        --no-first-run \
        --no-default-browser-check \
        "https://notebooklm.google.com" > /dev/null 2>&1 &

    # 等待启动
    for i in {1..15}; do
        sleep 1
        if check_cdp; then
            echo "✅ Chrome CDP 已启动"
            return 0
        fi
    done

    echo "❌ Chrome 启动失败"
    return 1
}

# 主逻辑
if ! check_cdp; then
    start_chrome || exit 1
fi

# 用 CDP 模式执行 nlm
exec "$REAL_NLM" --cdp-url "$CDP_URL" --no-auto-instance "$@"
