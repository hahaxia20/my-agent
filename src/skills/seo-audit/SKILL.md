---
name: seo-audit
description: Audit a page for SEO basics, keyword alignment, title and meta quality, heading structure, and content gaps. Use this skill for 页面SEO诊断 and search-oriented page improvement.
trigger_keywords:
  - seo audit
  - on-page seo
  - meta title
  - meta description
  - keyword gap
  - search ranking
  - 页面seo
  - seo诊断
  - seo优化
  - 标题描述优化
  - 关键词布局
use_strategy: |
  Route SEO audit requests here first and execute them through `web_scraper` and `web_search`.
  Scrape the target page to inspect titles, headings, visible copy, and structure, then use search when the user needs competitive or keyword context.
  Separate observed page facts from recommendations. Keep recommendations practical: title/meta, heading hierarchy, topic coverage, internal linking, and SERP alignment.
  If the user only wants a general webpage summary, prefer `web-content-analyzer`.
allowed_tools:
  - web_search
  - web_scraper
version: "1.0.0"
license: Proprietary. LICENSE.txt has complete terms
metadata: {}
---

# SEO Audit Skill

This skill is lightweight routing metadata only. Real execution lives in `web_search` and `web_scraper`.