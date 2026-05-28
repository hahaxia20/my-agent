"""
计算器工具 - 生产级实现
"""
from src.tools.base import BaseTool, ToolExecutionError
from typing import Any
import logging
import ast
import operator
import time

logger = logging.getLogger(__name__)


class CalculatorTool(BaseTool):
    """生产级计算器工具 - 支持安全数学计算"""

    def __init__(self):
        super().__init__()
        self.name = "calculator"
        self.description = "执行数学计算（加减乘除、幂运算、取余等）"

        self.parameters = {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式，例如: '2 + 2', '10 * 5', '2 ** 10'",
                    "minLength": 1,
                    "maxLength": 200
                }
            },
            "required": ["expression"]
        }

        self.timeout = 5  # 计算超时5秒
        self.retry_count = 1  # 重试1次

        # 允许的操作符
        self.operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.Mod: operator.mod,
            ast.FloorDiv: operator.floordiv,
        }

    def _safe_eval(self, expression: str) -> float:
        """安全的表达式求值（不使用 eval）"""
        try:
            # 解析表达式
            tree = ast.parse(expression, mode='eval')

            # 检查是否安全
            if not self._is_safe_expression(tree):
                raise ValueError("表达式包含不安全操作")

            # 执行计算
            result = self._eval_node(tree.body)

            # 处理浮点数精度
            if isinstance(result, float):
                result = round(result, 10)

            return result

        except SyntaxError as e:
            raise ValueError(f"表达式语法错误: {e}")
        except ZeroDivisionError:
            raise ValueError("除数不能为零")
        except Exception as e:
            raise ValueError(f"计算错误: {e}")

    def _is_safe_expression(self, node) -> bool:
        """检查表达式是否安全"""
        # 允许的节点类型
        allowed_nodes = (
            ast.Expression, ast.BinOp, ast.UnaryOp,
            ast.Num, ast.Constant,  # Constant 用于 Python 3.8+
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv,
            ast.USub, ast.UAdd
        )

        for child_node in ast.walk(node):
            if not isinstance(child_node, allowed_nodes):
                logger.warning(f"拒绝不安全的表达式节点: {type(child_node)}")
                return False

        return True

    def _eval_node(self, node):
        """递归计算 AST 节点"""
        if isinstance(node, ast.Constant):  # Python 3.8+
            return node.value
        elif isinstance(node, ast.Num):  # Python 3.7 及以下
            return node.n
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op = self.operators.get(type(node.op))
            if op is None:
                raise ValueError(f"不支持的操作符: {type(node.op)}")
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            elif isinstance(node.op, ast.UAdd):
                return +operand
        else:
            raise ValueError(f"不支持的表达式节点: {type(node)}")

    async def execute(self, expression: str, **kwargs) -> dict:
        """执行安全计算"""
        # 参数验证
        if not expression or not expression.strip():
            return {
                "success": False,
                "error": "表达式不能为空",
                "result": None
            }

        # 清理表达式
        expression = expression.strip()

        # 长度限制
        if len(expression) > 200:
            return {
                "success": False,
                "error": "表达式过长（最多200字符）",
                "result": None
            }

        try:
            # 记录开始时间
            start_time = time.time()

            logger.info(f"🧮 执行计算: {expression}")

            # 执行安全计算
            result = self._safe_eval(expression)

            execution_time = time.time() - start_time

            logger.info(f"✅ 计算完成: {expression} = {result}, 耗时 {execution_time:.3f}s")

            return {
                "success": True,
                "expression": expression,
                "result": result,
                "execution_time": round(execution_time, 3)
            }

        except ValueError as e:
            logger.warning(f"计算错误: {e}")
            return {
                "success": False,
                "expression": expression,
                "error": str(e),
                "result": None
            }
        except Exception as e:
            logger.error(f"计算异常: {e}", exc_info=True)
            return {
                "success": False,
                "expression": expression,
                "error": f"计算失败: {str(e)}",
                "result": None
            }