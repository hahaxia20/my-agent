from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from src.skills.manager import skill_registry

logger = logging.getLogger(__name__)


@dataclass
class WorkflowStep:
    name: str
    skill_name: str
    description: str


@dataclass
class WorkflowMatchConfig:
    intent_keywords: List[str] = field(default_factory=list)
    sequence_keywords: List[str] = field(default_factory=list)
    phase_groups: Dict[str, List[str]] = field(default_factory=dict)
    min_phase_hits: int = 2


@dataclass
class WorkflowDefinition:
    name: str
    description: str
    trigger_keywords: List[str] = field(default_factory=list)
    steps: List[WorkflowStep] = field(default_factory=list)
    match: WorkflowMatchConfig = field(default_factory=WorkflowMatchConfig)

    def match_query(self, query: str) -> Optional[str]:
        text = query.lower().strip()

        for keyword in self.trigger_keywords:
            if keyword and keyword.lower() in text:
                return f'trigger keyword: {keyword}'

        matched_intent = [kw for kw in self.match.intent_keywords if kw and kw.lower() in text]
        matched_sequence = [kw for kw in self.match.sequence_keywords if kw and kw.lower() in text]
        matched_phases = []
        for phase_name, keywords in self.match.phase_groups.items():
            if any(keyword and keyword.lower() in text for keyword in keywords):
                matched_phases.append(phase_name)

        if len(matched_phases) >= self.match.min_phase_hits and (matched_intent or matched_sequence):
            reasons = []
            if matched_intent:
                reasons.append(f'intent={matched_intent[:2]}')
            if matched_sequence:
                reasons.append(f'sequence={matched_sequence[:2]}')
            reasons.append(f'phases={matched_phases}')
            return '; '.join(reasons)

        return None


@dataclass
class WorkflowLoadReport:
    loaded: List[str] = field(default_factory=list)
    failed: List[Dict[str, str]] = field(default_factory=list)

    @property
    def total_attempted(self) -> int:
        return len(self.loaded) + len(self.failed)

    def summary(self) -> str:
        parts = [f'loaded {len(self.loaded)}/{self.total_attempted} workflows']
        if self.failed:
            fail_details = '; '.join(f"{item['name']}: {item['error']}" for item in self.failed)
            parts.append(f'failed: [{fail_details}]')
        return ' | '.join(parts)


class WorkflowRegistry:
    """Registry for fixed, reusable workflow definitions."""

    def __init__(self) -> None:
        self._workflows: Dict[str, WorkflowDefinition] = {}

    def register(self, workflow: WorkflowDefinition) -> None:
        self._workflows[workflow.name] = workflow
        logger.info('registered workflow: %s (%s steps)', workflow.name, len(workflow.steps))

    def get_workflow(self, workflow_name: str) -> Optional[WorkflowDefinition]:
        return self._workflows.get(workflow_name)

    def get_all(self) -> List[WorkflowDefinition]:
        return list(self._workflows.values())

    def clear(self) -> None:
        self._workflows.clear()

    def get_allowed_tools(self, workflow_name: str) -> List[str]:
        workflow = self.get_workflow(workflow_name)
        if not workflow:
            return []

        tools: List[str] = []
        seen = set()
        for step in workflow.steps:
            for tool_name in skill_registry.get_allowed_tools(step.skill_name):
                if tool_name in seen:
                    continue
                seen.add(tool_name)
                tools.append(tool_name)
        return tools

    def match_query(self, query: str) -> Optional[str]:
        matched = self.match_query_with_reason(query)
        return matched[0] if matched else None

    def match_query_with_reason(self, query: str) -> Optional[Tuple[str, str]]:
        for workflow in self.get_all():
            reason = workflow.match_query(query)
            if reason:
                return workflow.name, reason
        return None

    def get_workflows_metadata_list(self) -> str:
        workflows = self.get_all()
        if not workflows:
            return 'No active workflows'

        lines: List[str] = []
        for workflow in workflows:
            parts = [f'- **{workflow.name}**: {workflow.description}']
            if workflow.trigger_keywords:
                parts.append(f"triggers: {', '.join(workflow.trigger_keywords[:6])}")
            if workflow.steps:
                step_desc = ' -> '.join(f'{step.name}/{step.skill_name}' for step in workflow.steps)
                parts.append(f'steps: {step_desc}')
            allowed_tools = self.get_allowed_tools(workflow.name)
            if allowed_tools:
                parts.append(f"tools: {', '.join(allowed_tools)}")
            lines.append(' | '.join(parts))
        return '\n'.join(lines)

    def load_from_directory(self, workflows_dir: Path) -> WorkflowLoadReport:
        report = WorkflowLoadReport()
        if not workflows_dir.exists():
            logger.warning('workflow directory missing: %s', workflows_dir)
            return report

        for workflow_dir in workflows_dir.iterdir():
            if not workflow_dir.is_dir() or workflow_dir.name.startswith('__'):
                continue

            config_path = workflow_dir / 'WORKFLOW.yaml'
            if not config_path.exists():
                continue

            try:
                workflow = self._load_workflow_file(config_path)
                self.register(workflow)
                report.loaded.append(workflow.name)
            except Exception as exc:
                report.failed.append({'name': workflow_dir.name, 'error': str(exc)})
                logger.error('workflow load failure: %s - %s', workflow_dir.name, exc, exc_info=True)

        logger.info('%s <- %s', report.summary(), workflows_dir)
        return report

    def _load_workflow_file(self, config_path: Path) -> WorkflowDefinition:
        payload = yaml.safe_load(config_path.read_text(encoding='utf-8'))
        if not isinstance(payload, dict):
            raise ValueError(f'workflow config must be a YAML object: {config_path}')

        name = str(payload.get('name', '')).strip()
        description = str(payload.get('description', '')).strip()
        if not name:
            raise ValueError(f'workflow name missing: {config_path}')
        if not description:
            raise ValueError(f'workflow description missing: {config_path}')

        steps_data = payload.get('steps') or []
        if not isinstance(steps_data, list) or not steps_data:
            raise ValueError(f'workflow steps missing: {config_path}')

        steps: List[WorkflowStep] = []
        for index, step_data in enumerate(steps_data, start=1):
            if not isinstance(step_data, dict):
                raise ValueError(f'workflow step #{index} must be an object: {config_path}')
            step_name = str(step_data.get('name', '')).strip()
            skill_name = str(step_data.get('skill_name', '')).strip()
            step_description = str(step_data.get('description', '')).strip()
            if not step_name or not skill_name or not step_description:
                raise ValueError(f'workflow step #{index} incomplete: {config_path}')
            steps.append(WorkflowStep(name=step_name, skill_name=skill_name, description=step_description))

        match_data = payload.get('match') or {}
        if not isinstance(match_data, dict):
            raise ValueError(f'workflow match block must be an object: {config_path}')

        phase_groups_raw = match_data.get('phase_groups') or {}
        if not isinstance(phase_groups_raw, dict):
            raise ValueError(f'workflow phase_groups must be an object: {config_path}')
        phase_groups = {
            str(group_name): [str(item).strip() for item in keywords or [] if str(item).strip()]
            for group_name, keywords in phase_groups_raw.items()
        }

        match = WorkflowMatchConfig(
            intent_keywords=[str(item).strip() for item in match_data.get('intent_keywords', []) if str(item).strip()],
            sequence_keywords=[str(item).strip() for item in match_data.get('sequence_keywords', []) if str(item).strip()],
            phase_groups=phase_groups,
            min_phase_hits=int(match_data.get('min_phase_hits', 2)),
        )

        return WorkflowDefinition(
            name=name,
            description=description,
            trigger_keywords=[str(item).strip() for item in payload.get('trigger_keywords', []) if str(item).strip()],
            steps=steps,
            match=match,
        )


WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / 'workflows'
workflow_registry = WorkflowRegistry()
_init_report = workflow_registry.load_from_directory(WORKFLOWS_DIR)
logger.info('workflow bootstrap complete: %s workflows, failed=%s', len(workflow_registry.get_all()), len(_init_report.failed))