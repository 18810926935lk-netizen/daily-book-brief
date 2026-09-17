# 每日图书信息简报

每天北京时间 06:25 自动生成（GitHub Actions + GLM），发布到 GitHub Pages，经 Server酱推送到微信。

## 流程

1. `collect.py` 采集：Lit Hub 热文 / 播客榜单头部节目最新单集（iTunes RSS）/ NYT 榜首维基表
2. `gen_brief.py` 调 GLM（Anthropic 兼容端点）按 `PROMPT.md` 规范写稿（HTML + content.json）
3. `make_docx.py` 排版 docx
4. `notify.py` Server酱微信推送（摘要 + 全文链接）
5. 成品提交到 `site/`，经 GitHub Pages 发布

## Secrets / Variables

- `GLM_BASE_URL` / `GLM_TOKEN`：智谱 Anthropic 兼容端点与密钥
- `SERVERCHAN_KEY`：Server酱 SendKey
- 变量 `SITE_BASE`：Pages 基址（如 `https://<user>.github.io/daily-book-brief`）

格式基准见 `template/sample.html`（2026-09-16 样刊）。
