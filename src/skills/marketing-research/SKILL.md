---
name: marketing-research
description: Research markets, competitors, audience segments, positioning, and messaging opportunities. Use this skill for 市场调研, 竞品分析, 用户洞察, ICP, and go-to-market research.
trigger_keywords:
  - market research
  - competitor analysis
  - competitor research
  - audience research
  - icp
  - positioning
  - messaging
  - go-to-market
  - 市场调研
  - 竞品分析
  - 用户洞察
  - 用户画像
  - 产品定位
  - 卖点提炼
use_strategy: |
  Route marketing research requests here first and execute them through `web_search` and `web_scraper`.
  Use search to collect current market and competitor signals, then use scraping to inspect the most relevant pages directly.
  Structure the answer into: observed facts, competitor patterns, audience insight, positioning implications, and recommended next moves.
  If the user only wants copy generation, prefer `marketing-copywriting`. If the user asks for a content calendar, prefer `content-planner`.
allowed_tools:
  - web_search
  - web_scraper
version: "1.0.0"
license: Proprietary. LICENSE.txt has complete terms
metadata: {}
---

# Marketing Research Skill

This skill is lightweight routing metadata only. Real execution lives in `web_search` and `web_scraper`.