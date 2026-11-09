# 全球图书与文化简报

唯一生成端：GitHub Actions 调用 GLM，按 `PROMPT.md` 生成。北京时间06:00是计划启动时间，GitHub可能排队延迟。微信在页面发布并校验后推送；ChatGPT已有云端任务改为北京时间10:00读取同一份成稿。

## 数据与发布

- `collect_editorial.py` 检查NYT非虚构榜并解析Publishers Weekly精装非虚构完整25名；失败明确记录，不拿年度冠军汇总当最新排名。
- 同时采集11个图书、科研、教育、个人财务与跨文化RSS入口，保留日期、来源及正文/摘要边界。
- `telegram_web_source.py` 在运行器内下载、提取与去重；原始附件和片段不公开，失败可降级但状态必须展示。
- `gen_brief.py` 使用最新版 `PROMPT.md` 和空白样式模板 `template/current.html`；旧 `template/sample.html` 仅为历史样刊，不再注入生成。
- `publication.py` 插入完整榜单、检查必需栏目及已删除主题、导出同稿HTML/Markdown与SHA-256清单。
- `site/YYYY-MM-DD.json` 定位当日成稿；`latest.json` 仅作定位入口。文件名含版本指纹，重跑保留旧版本。
- `notify.py` 先核对页面字节和当天清单，再经Server酱发送摘要、版本与同版本全文链接。
- ChatGPT只读取当天清单和对应Markdown；未就绪时明确告知，禁止另写一份。定时任务是否实际读取成功须另查运行记录，不能仅凭保存提示词认定。

## 配置

既有密钥：`GLM_BASE_URL`、`GLM_TOKEN`、`SERVERCHAN_KEY`、`TELEGRAM_WEB_STATE`。变量：`SITE_BASE`、`TELEGRAM_ENABLED`、`TELEGRAM_SOURCE_MODE`。不要打印密钥或授权文件。

## 验证

`python -m unittest test_publication test_telegram_publications test_telegram_web_collection test_telegram_web_state test_telegram_source -v`

手动完整运行默认不发微信；仅需发送时选择 `send_notification=true`。Telegram诊断使用 `telegram_only=true`，不会生成或推送简报。

2026-11-09修复：此前ChatGPT与微信独立生成；微信旧提示词保留固定诺奖栏目和年度冠军拼榜。本次移除这些输入，增加完整非虚构榜、跨主题候选源与同稿版本校验。云端运行42566159605已生成版本8e3d2ca6c4e42cf5，Server酱返回HTTP200/code0/errno0；此回执不等同于证明用户已在微信阅读。
