---
name: web-content-analyzer
description: Analyze a webpage, summarize its main content, structure, claims, and visible information. Use this skill for general webpage reading or URL content analysis, not for full SEO audits.
trigger_keywords:
  - 分析网站
  - 分析网页
  - 网页分析
  - URL分析
  - website analysis
  - webpage summary
  - page content analysis
use_strategy: |
  When the user wants a webpage analyzed, use `web_scraper` to fetch the page content first.
  Base the answer on the fetched content, summarize the page clearly, and separate fetched facts from interpretation.
  Focus on page content, structure, claims, audience, and visible sections.
  If the user explicitly asks for SEO diagnosis, keyword gaps, title/meta optimization, or ranking-oriented advice, prefer `seo-audit` instead.
  Do not invent page details or claims that were not returned by the tool.
allowed_tools:
  - web_scraper
version: "2.0.0"
license: MIT
metadata:
  author: My Agent Team
---

# Web Content Analyzer

This skill only defines routing metadata and runtime strategy. Execution should happen through tools.