"""Owner-run fresh browser login; never reads an existing browser profile."""
import json
import subprocess
from telegram_web_state import filter_state

REPO = '18810926935lk-netizen/daily-book-brief'


def main():
    print('将打开全新的 Telegram 官方网页。请用手机扫码登录。')
    print('此登录授权具有账号级权限。仅认证数据将保存至上述仓库的 GitHub 加密 Secret，')
    print('不保存聊天记录或现有浏览器资料。云端仅测试指定频道附件，不发送微信。')
    print('可随时在 Telegram 设置 → 设备中撤销此会话。仓库：' + REPO)
    if input('同意此次专用云端授权，请输入 YES：').strip() != 'YES':
        return
    subprocess.run(['gh', 'auth', 'status'], check=True, capture_output=True)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto('https://web.telegram.org/a/', timeout=90000)
        input('扫码完成且看到聊天列表后，请回到此窗口按回车（不要开启网页锁屏密码）：')
        state = filter_state(context.storage_state())
        # Close before cloud restore: never run the same session concurrently.
        browser.close()
    payload = json.dumps(state, separators=(',', ':')).encode()
    if len(payload) > 47000:
        raise ValueError('authentication_state_too_large')
    subprocess.run(['gh', 'secret', 'set', 'TELEGRAM_WEB_STATE', '--repo', REPO],
                   input=payload, check=True, capture_output=True)
    subprocess.run(['gh', 'workflow', 'run', 'daily.yml', '--repo', REPO,
                    '-f', 'telegram_web_probe=true'], check=True, capture_output=True)
    print('授权已加密保存，两次独立云端验证已提交。每日采集尚未启用。')
    print('请回到对话告诉我“已扫码”，我会检查验证结果。')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Never print browser state, subprocess stderr, or exception messages.
        print('未完成：' + type(exc).__name__ + '。请回到对话排查，勿粘贴密钥。')
        raise SystemExit(1)
