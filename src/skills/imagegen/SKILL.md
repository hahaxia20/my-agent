---
name: imagegen
description: Generate new raster images inside the project workspace from natural-language prompts. Use this skill for posters, covers, illustrations, social-media cards, product mockups, key visuals, and other bitmap assets.
trigger_keywords:
  - imagegen
  - generate image
  - create image
  - make a poster
  - poster
  - illustration
  - cover image
  - social media card
  - key visual
  - kv
  - 生图
  - 生成图片
  - 生成海报
  - 画一张图
  - 配图
  - 海报
  - 主视觉
  - 核心主视觉
  - 视觉海报
  - 封面图
use_strategy: |
  Route bitmap-image generation requests here first and execute them through `imagegen_tool`.
  Turn the user's goal into a concrete visual prompt, then call the tool instead of only describing the image.
  Poster, key-visual, and main-visual requests should default here unless the user is explicitly asking for frontend code or a marketing strategy workflow.
  If the request is clearly about campaign strategy, channel packaging, launch angles, or social-media creative, prefer `social-creative`.
  Prefer saving outputs under the workspace and report the final file path clearly.
  Keep the answer concise: what was generated, where it was saved, and any notable constraints or uncertainty.
allowed_tools:
  - imagegen_tool
version: "1.0.0"
license: Proprietary. LICENSE.txt has complete terms
metadata: {}
---

# Image Generation Skill

This skill is lightweight routing metadata only. Real bitmap-image generation lives in `imagegen_tool`.