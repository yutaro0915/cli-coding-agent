"""
AI制御ワークフロー用のユーティリティ関数
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from workflow_types import StepType, StepDefinition, TaskDependency, DependencyType
from ai_workflow_controller import WorkflowController, CodeGenerationStep, FileOperationStep

logger = logging.getLogger(__name__)

def create_empty_workflow(goal: str, model_interface: Any) -> WorkflowController:
    """空のワークフローコントローラーを作成"""
    return WorkflowController(goal, model_interface)

def add_code_generation_step(workflow: WorkflowController, 
                            step_id: str, 
                            description: str, 
                            task: str,
                            language: str = "python",
                            output_variable: str = None) -> None:
    """コード生成ステップをワークフローに追加"""
    step = CodeGenerationStep(step_id, description, task, language, output_variable)
    workflow.add_step(step)

def add_file_operation_step(workflow: WorkflowController,
                           step_id: str,
                           description: str,
                           operation: str,
                           file_path: str,
                           content_variable: str = None) -> None:
    """ファイル操作ステップをワークフローに追加"""
    step = FileOperationStep(step_id, description, operation, file_path, content_variable)
    workflow.add_step(step)

def build_workflow_from_definitions(goal: str, 
                                   model_interface: Any,
                                   step_definitions: List[StepDefinition],
                                   dependencies: List[TaskDependency] = None) -> WorkflowController:
    """ステップ定義のリストからワークフローを構築"""
    workflow = create_empty_workflow(goal, model_interface)
    
    # ステップの追加
    for step_def in step_definitions:
        if step_def.type == StepType.CODE_GENERATION.value:
            add_code_generation_step(
                workflow,
                step_def.parameters.get("step_id", f"code_gen_{len(workflow.steps)}"),
                step_def.description,
                step_def.parameters.get("task", ""),
                step_def.parameters.get("language", "python"),
                step_def.parameters.get("output_variable")
            )
        elif step_def.type == StepType.FILE_OPERATION.value:
            add_file_operation_step(
                workflow,
                step_def.parameters.get("step_id", f"file_op_{len(workflow.steps)}"),
                step_def.description,
                step_def.parameters.get("operation", "write"),
                step_def.parameters.get("file_path", ""),
                step_def.parameters.get("content_variable")
            )
        # 他のステップタイプも同様に追加
    
    # 依存関係に基づいてステップ順序を最適化
    if dependencies:
        optimize_step_order(workflow, dependencies)
    
    return workflow

def optimize_step_order(workflow: WorkflowController, dependencies: List[TaskDependency]) -> None:
    """依存関係に基づいてステップ順序を最適化"""
    # 依存関係グラフを構築
    dependency_graph = {}
    for dep in dependencies:
        if dep.source_task_id not in dependency_graph:
            dependency_graph[dep.source_task_id] = []
        dependency_graph[dep.source_task_id].append(dep.target_task_id)
    
    # トポロジカルソートを使用して順序を決定
    visited = set()
    temp_mark = set()
    new_order = []
    
    def visit(node):
        if node in temp_mark:
            raise ValueError(f"ワークフローに循環依存関係があります: {node}")
        if node in visited:
            return
        
        temp_mark.add(node)
        
        for dependent in dependency_graph.get(node, []):
            if dependent in workflow.steps:
                visit(dependent)
        
        temp_mark.remove(node)
        visited.add(node)
        new_order.append(node)
    
    # 依存関係グラフがないノードも含める
    all_nodes = list(workflow.steps.keys())
    for node in all_nodes:
        if node not in visited:
            visit(node)
    
    # 順序を逆転して正しい実行順序にする
    workflow.step_order = list(reversed(new_order))

def export_workflow_to_json(workflow: WorkflowController, file_path: str) -> None:
    """ワークフローをJSONファイルにエクスポート"""
    workflow.save_to_file(file_path)

def import_workflow_from_json(file_path: str, model_interface: Any) -> WorkflowController:
    """JSONファイルからワークフローをインポート"""
    return WorkflowController.load_from_file(file_path, model_interface)
