---
name: pdf
description: Handle requests specifically about PDF files, such as reading, extracting, merging, splitting, form-filling, or OCR.
trigger_keywords:
  - pdf
  - .pdf
  - "\u5408\u5e76pdf"
  - "\u62c6\u5206pdf"
  - "\u63d0\u53d6pdf\u6587\u672c"
  - "\u586b\u5199pdf\u8868\u5355"
  - "PDF\u6587\u4ef6"
use_strategy: |
  Route PDF requests here first and execute them through `pdf_tool`.
  Prefer tool-backed answers for inspection, text extraction, table extraction, merge, and split.
  When summarizing extracted content, separate extracted facts from interpretation and mention page scope explicitly.
  If the PDF operation is outside current tool support, state that clearly instead of fabricating a result.
  If extraction returns partial or empty content, say so and recommend the next most relevant supported operation.
allowed_tools:
  - pdf_tool
version: "2.1.0"
license: Proprietary. LICENSE.txt has complete terms
metadata: {}
---

# PDF Skill

This skill is lightweight routing metadata only. Real PDF execution lives in `pdf_tool`.
