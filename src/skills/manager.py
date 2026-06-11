"""Skill 系统 - 注册表、解析器和实现"""

import yaml
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

@dataclass
class LoadReport:
    """Skill 加载报告"""
    loaded: List[str] = field(default_factory=list)
    failed: List[Dict[str, str]] = field(default_factory=list)

    @property
    def total_attempted(self) -> int:
        return len(self.loaded) + len(self.failed)

    def summary(self) -> str:
        parts = [f"加载 {len(self.loaded)}/{self.total_attempted} 个 Skills"]
        if self.failed:
            fail_details = "; ".join(f"{f['name']}: {f['error']}" for f in self.failed)
            parts.append(f"失败: [{fail_details}]")
        return "，".join(parts)


@dataclass
class ReloadReport:
    """Skill 热重载报告"""
    added: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    reloaded: List[str] = field(default_factory=list)
    failed: List[Dict[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        parts = []
        if self.added:
            parts.append(f"新增: {self.added}")
        if self.removed:
            parts.append(f"移除: {self.removed}")
        if self.reloaded:
            parts.append(f"刷新: {len(self.reloaded)} 个")
        if self.failed:
            parts.append(f"失败: {[f['name'] for f in self.failed]}")
        return " | ".join(parts) if parts else "无变化"


class SkillMetadata(BaseModel):
    """SKILL.md frontmatter 元数据"""
    name: str = Field(..., description="Skill 名称")
    description: str = Field(..., description="Skill 描述")
    version: Optional[str] = Field(None, description="语义化版本号，如 1.0.0")
    license: Optional[str] = Field(None, description="许可证")
    compatibility: Optional[str] = Field(None, description="兼容性要求")
    enabled: bool = Field(True, description="是否启用（可在 frontmatter 中声明默认禁用）")
    max_tokens: Optional[int] = Field(None, description="指令最大 token 数，超出则截断")
    metadata: Optional[Dict[str, str]] = Field(None, description="自定义元数据")
    allowed_tools: Optional[List[str]] = Field(
        default=None,
        description="本 Skill 配套使用的工具列表（渐进式引导，非强制限制）"
    )

    @validator('name')
    def validate_name(cls, v):
        if not v:
            raise ValueError("name 不能为空")
        if len(v) > 64:
            raise ValueError("name 不能超过 64 个字符")
        if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', v):
            raise ValueError("name 只能包含小写字母、数字和连字符")
        return v

    @validator('description')
    def validate_description(cls, v):
        if not v or not v.strip():
            raise ValueError("description 不能为空")
        if len(v) > 1024:
            raise ValueError("description 不能超过 1024 个字符")
        return v

    @validator('allowed_tools', pre=True)
    def validate_allowed_tools(cls, v):
        if v is None:
            return None
        # 支持逗号分隔字符串: "web_scraper, calculator"
        if isinstance(v, str):
            return [t.strip() for t in v.split(',') if t.strip()]
        return v


class SkillConfig(BaseModel):
    """完整的 Skill 配置"""
    metadata: SkillMetadata
    instructions: str = Field(..., description="Skill 指令内容")
    skill_path: Path = Field(..., description="Skill 目录路径")
    scripts: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    assets: List[str] = Field(default_factory=list)
    resolved_tools: List[str] = Field(
        default_factory=list,
        description="经验证存在的配套工具列表"
    )


# ==================== Skill 基类 ====================

class BaseSkill(ABC):
    """Skill 基类"""

    name: str
    description: str
    enabled: bool = True

    @abstractmethod
    async def execute(self, user_query: str, **kwargs) -> Any:
        """执行 Skill"""
        pass


# ==================== MarkdownSkill 实现 ====================

class MarkdownSkill(BaseSkill):
    """基于 SKILL.md 的 Skill"""

    def __init__(self, skill_path: Path):
        """初始化（只加载元数据）"""
        self.config = self._parse_skill_md(skill_path)

        # 阶段 1：只存储元数据
        self.name = self.config.metadata.name
        self.description = self.config.metadata.description
        self.enabled = self.config.metadata.enabled
        self.max_tokens = self.config.metadata.max_tokens
        self.resolved_tools = self.config.resolved_tools  # 经验证存在的工具
        self._instructions = None  # 延迟加载

        self.skill_path = skill_path
        self.scripts = self.config.scripts
        self.references = self.config.references
        self.assets = self.config.assets

        logger.info(f"✅ 加载 Skill 元数据: {self.name} (enabled={self.enabled})")

    def _parse_skill_md(self, skill_path: Path) -> SkillConfig:
        """解析 SKILL.md 文件"""
        md_file = skill_path / "SKILL.md"

        if not md_file.exists():
            raise FileNotFoundError(f"SKILL.md 不存在: {md_file}")

        content = md_file.read_text(encoding='utf-8')

        # 提取 frontmatter
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
        if not match:
            raise ValueError(f"SKILL.md 格式错误（缺少 frontmatter 分隔符 ---）: {md_file}")

        frontmatter_yaml = match.group(1)
        instructions = match.group(2).strip()

        # 解析 YAML
        try:
            metadata_dict = yaml.safe_load(frontmatter_yaml)
        except yaml.YAMLError as e:
            raise ValueError(f"SKILL.md frontmatter YAML 解析失败: {md_file} -> {e}") from e

        if not isinstance(metadata_dict, dict):
            raise ValueError(f"SKILL.md frontmatter 必须是 YAML 对象: {md_file}")

        try:
            metadata = SkillMetadata(**metadata_dict)
        except Exception as e:
            raise ValueError(f"SKILL.md 元数据校验失败: {md_file} -> {e}") from e

        # 提取 scripts 和 references
        scripts = self._extract_file_links(instructions, r'\[\$\.scripts/(.+?)\]')
        references = self._extract_file_links(instructions, r'\[\$\.references/(.+?)\]')
        assets = self._extract_file_links(instructions, r'\[\$\.assets/(.+?)\]')

        # 验证 allowed_tools 中声明的工具是否在 tool_manager 中存在
        resolved_tools = []
        allowed_tools = metadata.allowed_tools or []
        if allowed_tools:
            from src.tools.manager import tool_manager
            for tool_name in allowed_tools:
                if tool_manager.has_tool(tool_name):
                    resolved_tools.append(tool_name)
                else:
                    logger.warning(
                        f"⚠️ Skill '{metadata.name}' 声明的工具 '{tool_name}' 不存在，跳过"
                    )

        return SkillConfig(
            metadata=metadata,
            instructions=instructions,
            skill_path=skill_path,
            scripts=scripts,
            references=references,
            assets=assets,
            resolved_tools=resolved_tools
        )

    def _extract_file_links(self, text: str, pattern: str) -> List[str]:
        """提取文件链接"""
        return re.findall(pattern, text)

    async def execute(self, user_query: str, **kwargs) -> Any:
        """执行 Skill"""
        llm = kwargs.get("llm")
        settings = kwargs.get("settings")

        if not llm:
            return {"skill": self.name, "error": "缺少 LLM 客户端", "success": False}

        try:
            system_prompt = self._build_system_prompt()

            logger.info(f"🎯 执行 Skill: {self.name}")

            from langchain_core.messages import SystemMessage, HumanMessage

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_query)
            ]

            response = await llm.ainvoke(messages)

            logger.info(f"✅ Skill 执行完成: {self.name}")

            return {
                "skill": self.name,
                "result": response.content,
                "success": True,
                "metadata": {
                    "version": self.config.metadata.metadata.get("version") if self.config.metadata.metadata else None,
                    "author": self.config.metadata.metadata.get("author") if self.config.metadata.metadata else None
                }
            }

        except Exception as e:
            logger.error(f"❌ Skill 执行失败: {self.name} - {str(e)}", exc_info=True)
            return {"skill": self.name, "error": str(e), "success": False}

    def _build_system_prompt(self) -> str:
        """构建系统提示词（延迟加载完整指令，含长度保护）"""
        if self._instructions is None:
            logger.debug(f"📥 延迟加载 Skill 完整指令: {self.name}")
            self._instructions = self.config.instructions

        instructions = self._instructions

        # 指令长度保护：超过 max_tokens 时截断（1 token ≈ 2 汉字 / 4 英文字符，取近似 3 字符/token）
        if self.max_tokens:
            estimated_chars = self.max_tokens * 3
            if len(instructions) > estimated_chars:
                logger.warning(
                    f"⚠️ Skill '{self.name}' 指令长度 {len(instructions)} 字符，"
                    f"超过 max_tokens={self.max_tokens}（约 {estimated_chars} 字符），已截断"
                )
                instructions = instructions[:estimated_chars] + \
                    "\n\n...（指令已截断，完整内容请查看 SKILL.md）"

        metadata_info = f"# Skill: {self.name}\n{self.description}\n\n"
        return metadata_info + instructions


# ==================== SkillRegistry ====================

def _parse_version(version: Optional[str]) -> tuple:
    """将语义化版本字符串转为可比较的元组，None 视为 (0,)"""
    if not version:
        return (0,)
    try:
        return tuple(int(x) for x in version.split("."))
    except ValueError:
        return (0,)


class SkillRegistry:
    """Skill 注册表"""

    def __init__(self):
        self.skills: Dict[str, BaseSkill] = {}

    def get_skill(self, skill_name: str) -> Optional[BaseSkill]:
        """获取 Skill"""
        return self.skills.get(skill_name)

    def has_skill(self, skill_name: str) -> bool:
        """检查 Skill 是否存在"""
        return skill_name in self.skills

    def enable(self, skill_name: str) -> bool:
        """启用 Skill，返回是否成功"""
        skill = self.skills.get(skill_name)
        if not skill:
            return False
        skill.enabled = True
        logger.info(f"✅ Skill 已启用: {skill_name}")
        return True

    def disable(self, skill_name: str) -> bool:
        """禁用 Skill，返回是否成功"""
        skill = self.skills.get(skill_name)
        if not skill:
            return False
        skill.enabled = False
        logger.info(f"🚫 Skill 已禁用: {skill_name}")
        return True

    def get_active_skills(self) -> List[BaseSkill]:
        """获取所有已启用的 Skill"""
        return [s for s in self.skills.values() if s.enabled]

    def get_skills_metadata_list(self) -> str:
        """获取 Skill 元数据列表（用于系统提示词，仅含已启用 Skill，含配套工具提示）"""
        active = self.get_active_skills()
        if not active:
            return "暂无可用技能"

        skill_lines = []
        for skill in active:
            line = f"- **{skill.name}**: {skill.description}"
            if getattr(skill, 'resolved_tools', None):
                tools_str = ', '.join(f'`{t}`' for t in skill.resolved_tools)
                line += f"（配套工具: {tools_str}）"
            skill_lines.append(line)

        return "\n".join(skill_lines)

    def get_all(self) -> List[BaseSkill]:
        """获取所有 Skill（含已禁用）"""
        return list(self.skills.values())

    def load_from_directory(self, skills_dir: Path) -> LoadReport:
        """从目录加载 Skills，返回结构化加载报告"""
        report = LoadReport()

        if not skills_dir.exists():
            logger.warning(f"Skills 目录不存在: {skills_dir}")
            return report

        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            dir_name = skill_dir.name
            try:
                skill = MarkdownSkill(skill_dir)

                # 同名冲突处理：比较 version，保留高版本
                if skill.name in self.skills:
                    existing = self.skills[skill.name]
                    old_ver = getattr(existing, 'config', None)
                    old_ver_str = old_ver.metadata.version if old_ver else None
                    new_ver_str = skill.config.metadata.version

                    if _parse_version(new_ver_str) >= _parse_version(old_ver_str):
                        logger.warning(
                            f"⚠️ Skill '{skill.name}' 同名冲突，"
                            f"新版本 {new_ver_str or '(无)'} >= 旧版本 {old_ver_str or '(无)'}，覆盖"
                        )
                        self.skills[skill.name] = skill
                    else:
                        logger.warning(
                            f"⚠️ Skill '{skill.name}' 同名冲突，"
                            f"新版本 {new_ver_str or '(无)'} < 旧版本 {old_ver_str or '(无)'}，保留旧版本"
                        )
                else:
                    self.skills[skill.name] = skill

                report.loaded.append(skill.name)
                logger.info(f"✅ 加载 Skill: {skill.name}")

            except FileNotFoundError as e:
                report.failed.append({"name": dir_name, "error": f"文件缺失: {e}"})
                logger.error(f"❌ 加载 Skill 失败（文件缺失）: {dir_name} - {e}")
            except yaml.YAMLError as e:
                report.failed.append({"name": dir_name, "error": f"YAML 格式错误: {e}"})
                logger.error(f"❌ 加载 Skill 失败（YAML 格式错误）: {dir_name} - {e}")
            except ValueError as e:
                report.failed.append({"name": dir_name, "error": f"校验失败: {e}"})
                logger.error(f"❌ 加载 Skill 失败（校验失败）: {dir_name} - {e}")
            except Exception as e:
                report.failed.append({"name": dir_name, "error": str(e)})
                logger.error(f"❌ 加载 Skill 失败（未知错误）: {dir_name} - {e}", exc_info=True)

        logger.info(f"📦 {report.summary()} <- {skills_dir}")
        return report

    def reload(self, skills_dir: Optional[Path] = None) -> ReloadReport:
        """
        热重载：重新扫描目录，返回 ReloadReport。
        对比 reload 前后差异，报告新增/移除/刷新/失败的 Skill。
        """
        if skills_dir is None:
            skills_dir = Path(__file__).parent

        old_names = set(self.skills.keys())
        old_versions: Dict[str, Optional[str]] = {
            name: getattr(s, 'config', None) and s.config.metadata.version
            for name, s in self.skills.items()
        }

        self.skills.clear()
        load_report = self.load_from_directory(skills_dir)

        new_names = set(self.skills.keys())

        report = ReloadReport(
            added=sorted(new_names - old_names),
            removed=sorted(old_names - new_names),
            reloaded=sorted(new_names & old_names),
            failed=load_report.failed,
        )

        logger.info(f"🔄 Skill 热重载完成: {report.summary()}")
        return report


# ==================== 全局实例 ====================

skill_registry = SkillRegistry()

# 自动加载 Skills
SKILLS_DIR = Path(__file__).parent
_init_report = skill_registry.load_from_directory(SKILLS_DIR)

# 打印加载信息
print(f"\n🎯 总计加载 {len(skill_registry.get_all())} 个 Skills:")
for skill in skill_registry.get_all():
    status = "✅" if skill.enabled else "🚫"
    print(f"   {status} {skill.name}: {skill.description[:80]}...")
if _init_report.failed:
    print(f"⚠️ 加载失败: {_init_report.failed}")
