# Marketing Skill Cases

This file shows how the new marketing skills are meant to be used in the current project runtime.

## Skill Map

| Skill | Best for | Tools |
|---|---|---|
| `marketing-research` | market research, competitor analysis, audience insight, positioning | `web_search`, `web_scraper` |
| `marketing-copywriting` | ad copy, landing-page copy, slogans, hooks, CTAs | none |
| `seo-audit` | page SEO diagnosis and optimization suggestions | `web_search`, `web_scraper` |
| `content-planner` | content calendars, topic clusters, campaign series | none |
| `social-creative` | social campaign ideas, poster direction, optional visual generation | `imagegen_tool` |

## Conflict Boundaries

- `image-analysis`: use only when the task is to inspect or analyze an existing local image file.
- `imagegen`: use when the task is pure image generation with no marketing strategy context.
- `social-creative`: use when the task is campaign-led social creative, poster concepts, or channel-specific marketing assets.
- `web-content-analyzer`: use for generic webpage reading or structural analysis, not SEO diagnosis.
- `marketing-copywriting`: use for specific copy output, not multi-post planning.
- `content-planner`: use for calendars and series planning, not single ad-copy requests.

## Case 1: Marketing Research

User prompt:
`请帮我做国产 AI 知识库产品的竞品分析，重点看官网卖点、目标客户、定价线索和差异化定位。`

Expected skill:
`marketing-research`

Expected tool use:
`web_search`, `web_scraper`

Representative output shape:
- Observed competitor facts by brand
- Shared messaging patterns
- Likely ICP segments
- Positioning gap you can occupy
- Recommended next actions for GTM

## Case 2: Marketing Copywriting

User prompt:
`给一个面向中小企业老板的 CRM 产品写 5 个首页主标题和 5 个 CTA，风格要直接、有结果感。`

Expected skill:
`marketing-copywriting`

Representative output shape:
- 5 headline variants
- 5 supporting subhead lines
- 5 CTA variants
- Tone notes on where each variant fits

Sample output excerpt:
`主标题 1：把客户跟进从“靠记忆”变成“有结果的流程”`
`CTA 1：立即开始管理商机`

## Case 3: SEO Audit

User prompt:
`帮我审一下这个页面的 SEO：https://example.com/ai-crm，看看标题、描述、H1-H2 和内容覆盖有什么问题。`

Expected skill:
`seo-audit`

Expected tool use:
`web_scraper`, optionally `web_search`

Representative output shape:
- Observed page title / meta / headings
- Keyword-to-content alignment findings
- Missing topical sections
- Priority fixes ranked high / medium / low

## Case 4: Content Planner

User prompt:
`围绕“AI 销售助手”给我做一个 4 周内容日历，渠道包括公众号、小红书和官网博客。`

Expected skill:
`content-planner`

Representative output shape:
- Weekly theme
- Channel-specific post idea
- Funnel stage
- Core angle
- CTA or conversion goal

Sample output excerpt:
`第 1 周：主题 = 为什么销售团队开始需要 AI 助手`
`公众号：深度解释型文章`
`小红书：误区对比卡片`
`博客：解决方案落地指南`

## Case 5: Social Creative

User prompt:
`围绕“618 智能体工作流训练营”做一套社媒宣发创意，先给我 3 个海报方向，再生成其中一个黑金风格主海报。`

Expected skill:
`social-creative`

Expected tool use:
`imagegen_tool`

Representative output shape:
- 3 campaign hook directions
- Caption / CTA suggestions
- Selected visual prompt
- Generated output path when the user confirms a direction

Sample output excerpt:
`方向 A：黑金高势能，强调效率升级与职业竞争力`
`方向 B：冷白科技感，强调流程自动化`
`方向 C：红黑促销风，强调限时转化`
