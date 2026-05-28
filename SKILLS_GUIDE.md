# Agent Skills 使用指南

本指南介绍如何在项目中使用基于 **Agent Skills 规范** 的文件配置化 Skill 系统。

---

## 📋 目录

1. [概述](#概述)
2. [目录结构](#目录结构)
3. [创建新 Skill](#创建新-skill)
4. [SKILL.md 格式](#skillmd-格式)
5. [使用示例](#使用示例)
6. [高级功能](#高级功能)
7. [测试与验证](#测试与验证)

---

## 概述

基于 [Agent Skills 规范](https://agentskills.io/specification)，我们实现了一套文件配置的 Skill 系统：

✅ **优势**：
- 📝 通过 Markdown 文件定义 Skill，无需编写代码
- 🔄 自动加载，热插拔
- 📦 支持脚本、参考文档、静态资源
- 🔍 自动验证格式
- 🔙 向后兼容传统代码 Skill

---

## 目录结构

```
src/skills/
├── web-content-analyzer/          # Skill 目录（名称即 Skill name）
│   ├── SKILL.md                   # 必需：元数据 + 指令
│   ├── scripts/                   # 可选：可执行脚本
│   │   └── analyze.py
│   ├── references/                # 可选：参考文档
│   │   └── REFERENCE.md
│   └── assets/                    # 可选：静态资源
│       └── template.md
├── code_analysis.py               # 传统代码 Skill（向后兼容）
├── data_analysis.py
├── skill_parser.py                # SKILL.md 解析器
├── markdown_skill.py              # Markdown Skill 实现
├── manager.py                     # Skill 管理器
└── base.py                        # Skill 基类
```

---

## 创建新 Skill

### 步骤 1: 创建目录

```bash
mkdir src/skills/your-skill-name
```

**命名规则**：
- 小写字母、数字、连字符
- 不能以连字符开头或结尾
- 不能有连续连字符
- 最大 64 字符

✅ 有效：`web-content-analyzer`, `data-processor`, `code-review`  
❌ 无效：`Web-Analyzer`（大写）, `-pdf`（开头连字符）, `pdf--tool`（连续连字符）

### 步骤 2: 创建 SKILL.md

```bash
touch src/skills/your-skill-name/SKILL.md
```

### 步骤 3: 编写内容

```markdown
---
name: your-skill-name
description: 描述这个 Skill 做什么，何时使用它
license: MIT
metadata:
  author: Your Name
  version: "1.0.0"
---

# Your Skill Name

这里是详细的指令内容...

## 使用场景
- 场景 1
- 场景 2

## 执行步骤
1. 步骤 1
2. 步骤 2

## 输出格式
按照以下格式输出结果...
```

### 步骤 4: 自动加载

**无需额外配置！** 系统启动时会自动扫描 `src/skills/` 目录并加载所有有效的 Skill。

---

## SKILL.md 格式

### Frontmatter（必需）

```yaml
---
name: skill-name                    # 必需，1-64 字符
description: Skill 描述              # 必需，1-1024 字符
license: MIT                        # 可选
compatibility: Requires Python 3.10+ # 可选
metadata:                           # 可选，自定义键值对
  author: Your Name
  version: "1.0.0"
  category: web-analysis
allowed-tools: Read Write           # 可选（实验性）
---
```

### Body（Markdown 指令）

Markdown 正文包含 Skill 的详细指令，建议：
- ✅ 保持在 500 行以内
- ✅ 包含使用场景、执行步骤、输出格式
- ✅ 提供示例和常见错误处理
- ✅ 将长内容拆分到 `references/` 目录

---

## 使用示例

### 示例 1: 网页内容分析器

已实现的完整示例：[web-content-analyzer](src/skills/web-content-analyzer/)

**SKILL.md 片段**：
```yaml
---
name: web-content-analyzer
description: Analyze web page content, extract key information, summarize content, and detect SEO issues.
license: MIT
metadata:
  author: My Agent Team
  version: "1.0.0"
---
```

**文件结构**：
```
web-content-analyzer/
├── SKILL.md           # 102 行，包含完整指令
└── scripts/
    └── analyze.py     # 辅助脚本
```

### 示例 2: 创建你的第一个 Skill

```bash
# 1. 创建目录
mkdir src/skills/my-custom-skill

# 2. 创建 SKILL.md
cat > src/skills/my-custom-skill/SKILL.md << 'EOF'
---
name: my-custom-skill
description: 我的自定义 Skill，用于处理特定任务
metadata:
  author: Me
  version: "1.0.0"
---

# My Custom Skill

## 功能
处理用户的特定请求...

## 使用方法
1. 接收用户输入
2. 处理数据
3. 返回结果
EOF

# 3. 重启服务，自动加载
python run.py
```

---

## 高级功能

### 1. 添加脚本文件

在 `scripts/` 目录下放置 Python/Bash 脚本：

```
my-skill/
├── SKILL.md
└── scripts/
    ├── preprocess.py
    └── postprocess.sh
```

在 SKILL.md 中引用：
```markdown
运行预处理脚本：
scripts/preprocess.py
```

### 2. 添加参考文档

将长篇内容拆分到 `references/`：

```
my-skill/
├── SKILL.md              # 主指令（< 500 行）
└── references/
    ├── REFERENCE.md      # 技术参考
    ├── FORMS.md          # 表单模板
    └── examples.md       # 示例集合
```

### 3. 添加静态资源

在 `assets/` 放置模板、图片等：

```
my-skill/
├── SKILL.md
└── assets/
    ├── report-template.md
    ├── config-schema.json
    └── diagram.png
```

### 4. 验证 Skill

使用内置验证器检查格式：

```python
from pathlib import Path
from src.skills.skill_parser import SkillParser

skill_path = Path("src/skills/my-skill")
is_valid, errors = SkillParser.validate_skill(skill_path)

if is_valid:
    print("✅ Skill 格式正确")
else:
    print("❌ 验证失败:")
    for error in errors:
        print(f"   - {error}")
```

---

## 测试与验证

### 运行测试套件

```bash
python -m src.test_skills
```

测试内容：
1. ✅ SKILL.md 解析器
2. ✅ SkillManager 自动加载
3. ✅ Skill 执行流程
4. ✅ Skill 信息查询

### 查看已加载的 Skills

启动服务后，控制台会显示：

```
🎯 总计加载 3 个 Skills:
   📝 Markdown web-content-analyzer: Analyze web page content...
   💻 Code code_analysis: 分析代码质量、提供改进建议...
   💻 Code data_analysis: 分析数据并提供可视化建议...
```

- 📝 **Markdown**: 基于 SKILL.md 的 Skill
- 💻 **Code**: 传统代码 Skill

### 在代码中使用

```python
from src.skills.manager import skill_manager

# 获取所有 Skills
all_skills = skill_manager.get_all()

# 获取特定 Skill
skill = skill_manager.get_skill("web-content-analyzer")

# 查看 Skill 信息
if hasattr(skill, 'get_skill_info'):
    info = skill.get_skill_info()
    print(f"名称: {info['name']}")
    print(f"路径: {info['path']}")
    print(f"有脚本: {info['has_scripts']}")

# 执行 Skill
result = await skill.execute(
    user_query="请分析这个网页: https://example.com",
    llm=llm_client,
    settings=settings
)
```

---

## 向后兼容

系统同时支持：
1. ✅ **Markdown Skills**（推荐）：通过 SKILL.md 文件配置
2. ✅ **代码 Skills**（兼容）：继承 BaseSkill 的 Python 类

同名 Skill 优先使用 Markdown 版本。

---

## 最佳实践

1. **保持 SKILL.md 简洁**：主文件 < 500 行，详细内容放 `references/`
2. **描述要具体**：说明"做什么"和"何时使用"
3. **提供示例**：包含输入输出示例
4. **错误处理**：说明常见错误和解决方案
5. **版本管理**：在 metadata 中标注版本号
6. **测试验证**：创建后运行 `test_skills.py` 验证

---

## 故障排除

### Q: Skill 没有被加载？

检查：
1. 目录名是否符合命名规则？
2. 是否存在 SKILL.md 文件？
3. frontmatter 格式是否正确？
4. name 字段是否与目录名一致？

### Q: 验证失败？

运行测试查看具体错误：
```python
from src.skills.skill_parser import SkillParser
is_valid, errors = SkillParser.validate_skill(path)
print(errors)
```

### Q: 如何调试 Skill 执行？

查看日志：
```bash
# 日志文件
cat logs/agent.log | grep "Skill"
```

---

## 相关文档

- [Agent Skills 规范](https://agentskills.io/specification)
- [Skill 解析器实现](src/skills/skill_parser.py)
- [Markdown Skill 实现](src/skills/markdown_skill.py)
- [Skill Manager](src/skills/manager.py)
- [测试脚本](tests/test_skills.py)

---

**祝使用愉快！** 🎉
