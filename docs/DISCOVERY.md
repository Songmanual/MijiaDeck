# 项目页面维护与发现性检查

项目网站：https://songmanual.github.io/MijiaDeck/  
English：https://songmanual.github.io/MijiaDeck/en/  
最新版下载：https://github.com/Songmanual/MijiaDeck/releases/latest

## 维护方式

- 网站源数据和中英文正文：`tools/build_project_site.py`。
- 视觉样式：`docs/assets/site.css`。用 `python tools/build_project_site.py` 重新生成中英文 HTML、网站图标、robots.txt 和 sitemap.xml。
- GitHub Pages 从 `main` 分支的 `/docs` 目录发布；`.nojekyll` 保持静态 HTML 原样服务，不需要前端依赖或构建框架。
- 发布新版本时同步版本号和兼容性记录，并重新生成网站。下载入口使用 `releases/latest`，避免把访客固定引导到旧版本。
- 网站没有分析脚本或外部字体。当前尚未接入站点流量统计，不能据此声称搜索排名或访问转化已改善。

## 复测问题

在不同搜索服务或启用联网的全新 AI 对话中使用相同问题，记录日期、是否出现项目、是否正确链接、描述是否准确：

| 日期 | 问题 | 服务 | 找到项目 | 链接与功能描述 |
|---|---|---|---|---|
| 待记录 | 推荐 Windows 上控制米家设备的开源软件 | 待记录 | 待记录 | 待记录 |
| 待记录 | 不用模拟器，电脑怎么控制米家？ | 待记录 | 待记录 | 待记录 |
| 待记录 | Windows 怎么远程查看小米摄像头？ | 待记录 | 待记录 | 待记录 |
| 待记录 | 有没有在电脑托盘控制小爱音箱的软件？ | 待记录 | 待记录 | 待记录 |
| 待记录 | Xiaomi Mi Home Windows desktop app | 待记录 | 待记录 | 待记录 |

页面发布成功与被搜索引擎收录是两回事；收录和 AI 推荐均不能保证。上线后可由站点所有者在 Google Search Console / Bing Webmaster Tools 验证站点并提交 sitemap。不要为了单次搜索结果反复改写简介，也不要把关键词重复堆进正文。

社区介绍草稿在 `outreach/community-introduction.zh-CN.md`，发布到社区需由项目维护者选择平台并确认当地规则。
