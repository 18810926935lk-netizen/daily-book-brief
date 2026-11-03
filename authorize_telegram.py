"""Run interactively by the account owner. Never print or write session secrets."""
import asyncio
from getpass import getpass
import json
import logging
import subprocess
import sys
from urllib.parse import urlparse

REPO = '18810926935lk-netizen/daily-book-brief'


def gh(*args, secret=None):
    proc = subprocess.run(['gh', *args], input=secret, text=True, encoding='utf-8',
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode:
        raise RuntimeError('GitHub 操作失败，请检查 gh 登录及仓库权限；敏感输出已隐藏。')
    return proc.stdout.strip()


async def authorize():
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import SessionPasswordNeededError
    logging.getLogger('telethon').setLevel(logging.CRITICAL)
    gh('api', 'user', '--jq', '.login')
    print('仅接入频道 demagazinesharing。不会发送 Telegram 消息。')
    print('凭据将加密保存到原 GitHub 仓库的 Actions Secrets，不写入本地文件。')
    print('注意：Telegram 会话具备账号级访问能力，并非仅限该频道。')
    print('可在 Telegram 设置 → 设备 中撤销 Daily brief channel reader 会话。')
    if input('同意创建会话并保存至 ' + REPO + '？输入 YES：').strip() != 'YES':
        print('已取消，未创建会话。')
        return
    api_id = int(getpass('api_id（输入不显示）：').strip())
    api_hash = getpass('api_hash（输入不显示）：').strip()
    proxy_text = input('如需代理，输入本机 SOCKS5 地址，如 socks5://127.0.0.1:7897；无需则回车：').strip()
    proxy = None
    if proxy_text:
        parsed = urlparse(proxy_text)
        if parsed.scheme != 'socks5' or parsed.hostname not in ('localhost', '127.0.0.1') or not parsed.port:
            raise ValueError('只支持明确指定的本机 SOCKS5 代理')
        proxy = {'proxy_type': 'socks5', 'addr': parsed.hostname, 'port': parsed.port}
    client = TelegramClient(StringSession(), api_id, api_hash, proxy=proxy,
                            device_model='Daily brief channel reader', receive_updates=False,
                            connection_retries=2, request_retries=2)
    uploaded = False
    await client.connect()
    try:
        phone = getpass('Telegram 手机号（含国家码，输入不显示）：').strip()
        await client.send_code_request(phone)
        try:
            await client.sign_in(phone, getpass('Telegram 收到的登录验证码（输入不显示）：').strip())
        except SessionPasswordNeededError:
            await client.sign_in(password=getpass('Telegram 两步验证密码（输入不显示）：'))
        channel = await client.get_entity('demagazinesharing')
        messages = await client.get_messages(channel, limit=3)
        print('频道连接验证成功，读取到', len(messages), '条近期消息。')
        auth = json.dumps({'api_id': api_id, 'api_hash': api_hash, 'session': client.session.save()})
        gh('secret', 'set', 'TELEGRAM_AUTH_JSON', '-R', REPO, secret=auth)
        uploaded = True
        gh('variable', 'set', 'TELEGRAM_ENABLED', '-R', REPO, '--body', 'true')
        gh('workflow', 'run', 'daily.yml', '-R', REPO, '-f', 'telegram_only=true')
        print('授权已保存；已启动仅检查 Telegram 的云端验证，不会发送微信。')
        print('请回到聊天告诉助手“授权完成”，继续核验下载与正文提取。')
    finally:
        if not uploaded and await client.is_user_authorized():
            await client.log_out()
        await client.disconnect()


if __name__ == '__main__':
    try:
        asyncio.run(authorize())
    except (Exception, KeyboardInterrupt) as exc:
        print('未完成全部步骤：', type(exc).__name__, '。敏感错误详情已隐藏。')
        print('如已看到“频道连接验证成功”，可回到聊天检查配置状态。')
        sys.exit(1)
