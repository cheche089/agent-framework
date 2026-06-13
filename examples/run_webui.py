"""OpenAgent Web UI - 启动脚本
像 Codex 桌面版一样的图形界面
"""

import os, sys, subprocess, webbrowser, time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WEB_UI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web_ui")

def main():
    print("=" * 60)
    print("  OpenAgent Web UI")
    print("  像 Codex 桌面版一样的 AI 助手界面")
    print("=" * 60)
    print()
    print("  支持的厂商: OpenAI, DeepSeek, \u901a\u4e49\u5343\u95ee, \u667a\u8c31 GLM,")
    print("              Moonshot Kimi, Anthropic Claude, Google Gemini, \u8c46\u5305")
    print()
    print("  \u2705 流式输出  |  \u2705 对话管理  |  \u2705 多模型切换")
    print()

    # Check if web_ui exists
    if not os.path.exists(WEB_UI_DIR):
        print(f"  [!] web_ui directory not found at: {WEB_UI_DIR}")
        print("  Please run this script from the project root.")
        sys.exit(1)

    main_py = os.path.join(WEB_UI_DIR, "main.py")
    if not os.path.exists(main_py):
        print(f"  [!] main.py not found at: {main_py}")
        sys.exit(1)

    print("  Starting server on http://127.0.0.1:8080 ...")
    print("  Press Ctrl+C to stop.")
    print()

    # Open browser after a short delay
    def open_browser():
        time.sleep(2)
        webbrowser.open("http://127.0.0.1:8080")

    import threading
    t = threading.Thread(target=open_browser, daemon=True)
    t.start()

    # Start uvicorn
    os.chdir(WEB_UI_DIR)
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8080, log_level="info")

if __name__ == "__main__":
    main()
