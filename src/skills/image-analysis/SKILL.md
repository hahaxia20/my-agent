---
name: image-analysis
description: Analyze local image files and uploaded screenshots or photos. Use this skill for 图片分析, image inspection, OCR-style reading, and visual content understanding of an existing image.
trigger_keywords:
  - image analysis
  - analyze image
  - inspect image
  - image inspection
  - screenshot analysis
  - photo analysis
  - 图片分析
  - 分析图片
  - 截图分析
  - 照片分析
  - 识别图片内容
use_strategy: |
  Route local image-file analysis requests here first and execute them through `image_tool`.
  Prefer tool-backed answers for existing uploaded images instead of generic guesses.
  For analysis requests, structure the answer into: visible facts, visible text, layout/composition, notable details, and limitations.
  Distinguish clearly between what is directly visible and what is inferred.
  If the image is blurry, cropped, or too small, say which parts cannot be judged reliably.
  If the image is specifically a stock chart with K-line, MA, MACD, volume, or chip-distribution signals, prefer `stock-analysis` instead.
  If the user wants to create a new image, poster, cover, or main visual, prefer `imagegen` instead.
  Do not fabricate text, identities, locations, or exact numbers that are not legible in the image.
allowed_tools:
  - image_tool
version: "1.0.0"
license: Proprietary. LICENSE.txt has complete terms
metadata: {}
---

# Image Analysis Skill

This skill is lightweight routing metadata only. Real image analysis execution lives in `image_tool`.