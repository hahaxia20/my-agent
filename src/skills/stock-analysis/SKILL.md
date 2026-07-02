---
name: stock-analysis
description: Analyze uploaded stock-chart images that contain candlesticks, MA20/MA60, volume, MACD, and same-day chip-distribution visuals.
trigger_keywords:
  - stock chart analysis
  - candlestick analysis
  - kline analysis
  - stock technical chart
  - stock trend chart
  - macd analysis
  - chip distribution analysis
  - ma20 ma60
  - 股票K线分析
  - 股票图分析
  - K线分析
  - 均线分析
  - MACD分析
  - 筹码峰分析
  - 股票技术分析
use_strategy: |
  Route stock-chart screenshot requests here first and use `image_tool` as the only execution tool.
  This skill is only for financial chart interpretation of stock screenshots, not for general image inspection and not for generating visuals.
  Analyze the chart with a disciplined technical-review structure rather than a trading-call style.
  Start from observable facts in the image, then provide restrained interpretation, and end with key risks or uncertainty.

  Cover these dimensions in order:
  1. Price structure and candlestick behavior: describe the recent trend state, the strength or weakness of the latest bars,
     whether the structure looks like continuation, consolidation, breakout attempt, or distribution, and whether there are
     obvious long upper shadows, long lower shadows, gaps, or volatility expansion.
  2. MA20 and MA60: assess relative position, slope, distance, and whether price is trading above, below, or around the moving
     averages. Comment on whether MA20 is supporting momentum, whether MA60 acts as medium-term support/resistance, and whether
     there are signs of golden-cross, dead-cross, adhesion, or divergence.
  3. Volume: evaluate whether turnover confirms the price move. Distinguish between healthy expansion, weak rebound on low volume,
     breakout without confirmation, or heavy-volume selling. Note any obvious mismatch between price direction and volume change.
  4. MACD: assess DIF/DEA relationship, histogram expansion or contraction, whether momentum is strengthening or weakening, and
     whether there are visible early signs of bullish or bearish divergence. Avoid claiming divergence unless it is reasonably visible.
  5. Same-day chip distribution: comment on chip concentration versus dispersion, the likely cost concentration zone, whether chips
     appear to migrate upward, and whether the current price seems above, inside, or below the main chip area. Use cautious language,
     because chip-peak interpretation is sensitive to image clarity and platform rendering.

  Output style requirements:
  - Separate "Visible facts" from "Interpretation".
  - Be professional, neutral, and evidence-based.
  - Do not fabricate exact prices, dates, percentage moves, or signals that are not legible in the image.
  - Do not give absolute buy/sell recommendations or certainty language.
  - If the image is cropped, blurry, or partial, explicitly state what cannot be reliably judged.
  - When appropriate, conclude with a short summary of current trend bias, confirmation conditions, and invalidation/risk points.
  - If the request is about a normal screenshot, photo, scanned document, or OCR-style image reading, prefer `image-analysis` instead.
allowed_tools:
  - image_tool
version: "1.0.0"
license: Proprietary. LICENSE.txt has complete terms
metadata: {}
---

# Stock Analysis Skill

This skill is lightweight routing metadata only. Runtime execution should call `image_tool`
against a local uploaded chart image and interpret the visible K-line, moving averages,
volume, MACD, and chip-distribution information.