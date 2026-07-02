---
name: social-creative
description: Create social campaign concepts, post angles, captions, launch poster directions, and optional image-generation requests for marketing visuals.
trigger_keywords:
  - social creative
  - campaign creative
  - social campaign
  - social post idea
  - launch poster
  - campaign visual
  - social poster
  - campaign poster
  - launch visual
  - 社媒创意
  - 社媒海报
  - 宣发创意
  - 小红书文案
  - 社媒配图
  - 宣发海报
use_strategy: |
  Route marketing-led social creative requests here first and execute visual generation through `imagegen_tool` when the user explicitly wants assets.
  Start from objective, audience, channel, and hook. Then provide angle, caption, CTA, visual direction, and optional generation prompt.
  Use `imagegen_tool` only when the user asks for an actual poster or visual asset. If the user only wants raw image generation with no campaign context, prefer `imagegen`.
  If the user only wants to inspect an existing image, prefer `image-analysis`.
allowed_tools:
  - imagegen_tool
version: "1.0.0"
license: Proprietary. LICENSE.txt has complete terms
metadata: {}
---

# Social Creative Skill

This skill is lightweight routing metadata only. Real visual generation execution lives in `imagegen_tool`.