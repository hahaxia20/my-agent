"""Skill 系统 - 注册表、解析器和实现"""

import yaml
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

class SkillMetadata(BaseModel):
    """SKILL.md frontmatter 元数据"""
    name: str = Field(..., description="Skill 名称")
    description: str = Field(..., description="Skill 描述")
    license: Optional[str] = Field(None, description="许可证")
    compatibility: Optional[str] = Field(None, description="兼容性要求")
    metadata: Optional[Dict[str, str]] = Field(None, description="自定义元数据")
    allowed_tools: Optional[str] = Field(None, description="允许使用的工具列表")

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


class SkillConfig(BaseModel):
    """完整的 Skill 配置"""
    metadata: SkillMetadata
    instructions: str = Field(..., description="Skill 指令内容")
    skill_path: Path = Field(..., description="Skill 目录路径")
    scripts: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    assets: List[str] = Field(default_factory=list)


# ==================== Skill 基类 ====================

class BaseSkill(ABC):
    """Skill 基类"""
    
    name: str
    description: str
    
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
        self._instructions = None  # 延迟加载
        
        self.skill_path = skill_path
        self.scripts = self.config.scripts
        self.references = self.config.references
        self.assets = self.config.assets
        
        logger.info(f"✅ 加载 Skill 元数据: {self.name}")
    
    def _parse_skill_md(self, skill_path: Path) -> SkillConfig:
        """解析 SKILL.md 文件"""
        md_file = skill_path / "SKILL.md"
        
        if not md_file.exists():
            raise FileNotFoundError(f"SKILL.md 不存在: {md_file}")
        
        content = md_file.read_text(encoding='utf-8')
        
        # 提取 frontmatter
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
        if not match:
            raise ValueError(f"SKILL.md 格式错误: {md_file}")
        
        frontmatter_yaml = match.group(1)
        instructions = match.group(2).strip()
        
        # 解析 YAML
        metadata_dict = yaml.safe_load(frontmatter_yaml)
        metadata = SkillMetadata(**metadata_dict)
        
        # 提取 scripts 和 references
        scripts = self._extract_file_links(instructions, r'\[\$\.scripts/(.+?)\]')
        references = self._extract_file_links(instructions, r'\[\$\.references/(.+?)\]')
        assets = self._extract_file_links(instructions, r'\[\$\.assets/(.+?)\]')
        
        return SkillConfig(
            metadata=metadata,
            instructions=instructions,
            skill_path=skill_path,
            scripts=scripts,
            references=references,
            assets=assets
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
        """构建系统提示词（延迟加载完整指令）"""
        if self._instructions is None:
            logger.debug(f"📥 延迟加载 Skill 完整指令: {self.name}")
            self._instructions = self.config.instructions
        
        metadata_info = f"# Skill: {self.name}\n{self.description}\n\n"
        return metadata_info + self._instructions


# ==================== SkillRegistry ====================

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
    
    def get_skills_metadata_list(self) -> str:
        """获取 Skill 元数据列表（用于系统提示词）"""
        if not self.skills:
            return "暂无可用技能"
        
        skill_lines = []
        for skill in self.skills.values():
            skill_lines.append(f"- **{skill.name}**: {skill.description}")
        
        return "\n".join(skill_lines)
    
    def get_all(self) -> List[BaseSkill]:
        """获取所有 Skill"""
        return list(self.skills.values())
    
    def load_from_directory(self, skills_dir: Path) -> int:
        """从目录加载 Skills"""
        if not skills_dir.exists():
            logger.warning(f"Skills 目录不存在: {skills_dir}")
            return 0
        
        loaded_count = 0
        
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            
            try:
                skill = MarkdownSkill(skill_dir)
                self.skills[skill.name] = skill
                loaded_count += 1
                logger.info(f"✅ 加载 Skill: {skill.name}")
                    
            except Exception as e:
                logger.error(f"❌ 加载 Skill 失败: {skill_dir.name} - {str(e)}", exc_info=True)
        
        logger.info(f"📦 从目录加载了 {loaded_count} 个 Skills: {skills_dir}")
        return loaded_count


# ==================== 全局实例 ====================

skill_registry = SkillRegistry()

# 自动加载 Skills
SKILLS_DIR = Path(__file__).parent
skill_registry.load_from_directory(SKILLS_DIR)

# 打印加载信息
all_skills = skill_registry.get_all()
print(f"\n🎯 总计加载 {len(all_skills)} 个 Skills:")
for skill in all_skills:
    print(f"   📝 {skill.name}: {skill.description[:80]}...")
