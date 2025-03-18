"""
AI制御ワークフロー機能のコントローラーモジュール
ユーザーの目標からAIが自律的にタスクを計画・実行・評価する機能を提供
"""

import json
import logging
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

class WorkflowStepStatus(Enum):
    """ワークフローステップのステータス"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class WorkflowContext:
    """ワークフローの実行コンテキスト"""
    variables: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    
    def get_variable(self, name: str, default: Any = None) -> Any:
        """コンテキスト変数を取得"""
        return self.variables.get(name, default)
        
    def set_variable(self, name: str, value: Any) -> None:
        """コンテキスト変数を設定"""
        self.variables[name] = value
        
    def set_result(self, step_id: str, result: Any) -> None:
        """ステップの結果を保存"""
        self.results[step_id] = result
        
    def get_result(self, step_id: str, default: Any = None) -> Any:
        """ステップの結果を取得"""
        return self.results.get(step_id, default)

class WorkflowStep:
    """ワークフローステップの基底クラス"""
    
    def __init__(self, step_id: str, description: str):
        self.step_id = step_id
        self.description = description
        self.status = WorkflowStepStatus.PENDING
        self.result = None
        self.error = None
        
    def execute(self, context: WorkflowContext) -> bool:
        """ステップを実行（サブクラスでオーバーライド）"""
        raise NotImplementedError("This method must be implemented by subclasses")
        
    def to_dict(self) -> Dict:
        """ステップをディクショナリに変換"""
        return {
            "step_id": self.step_id,
            "type": self.__class__.__name__,
            "description": self.description,
            "status": self.status.value
        }
        
    @classmethod
    def from_dict(cls, data: Dict) -> 'WorkflowStep':
        """ディクショナリからステップを作成"""
        step_type = data.get("type", "")
        # ステップタイプに基づいて適切なサブクラスのインスタンスを作成
        step_class = STEP_TYPE_REGISTRY.get(step_type)
        if not step_class:
            raise ValueError(f"未知のステップタイプ: {step_type}")
        
        return step_class.create_from_dict(data)

class CodeGenerationStep(WorkflowStep):
    """コード生成ステップ"""
    
    def __init__(self, step_id: str, description: str, task: str, 
                 language: str = "python", output_variable: str = None):
        super().__init__(step_id, description)
        self.task = task
        self.language = language
        self.output_variable = output_variable or f"{step_id}_code"
        
    def execute(self, context: WorkflowContext) -> bool:
        """コード生成ステップを実行"""
        self.status = WorkflowStepStatus.IN_PROGRESS
        try:
            # モデルインターフェースからアクセス
            model = context.get_variable("model_interface")
            if not model:
                self.error = "モデルインターフェースがコンテキストに設定されていません"
                self.status = WorkflowStepStatus.FAILED
                return False
                
            # コード生成プロンプトを作成
            prompt = f"{self.language}で{self.task}を実装するコードを生成してください。"
            
            # モデルを使用してコード生成
            response = model.generate_content(prompt).text.strip()
            
            # コードを抽出（tools.pyの関数を再利用）
            from tools import clean_code_output
            code = clean_code_output(response)
            
            # 結果をコンテキストに保存
            context.set_variable(self.output_variable, code)
            context.set_result(self.step_id, {
                "code": code,
                "raw_response": response
            })
            
            self.result = code
            self.status = WorkflowStepStatus.COMPLETED
            return True
            
        except Exception as e:
            self.error = str(e)
            self.status = WorkflowStepStatus.FAILED
            return False
            
    def to_dict(self) -> Dict:
        """ステップをディクショナリに変換（オーバーライド）"""
        data = super().to_dict()
        data.update({
            "task": self.task,
            "language": self.language,
            "output_variable": self.output_variable
        })
        return data
        
    @classmethod
    def create_from_dict(cls, data: Dict) -> 'CodeGenerationStep':
        """ディクショナリからステップを作成"""
        return cls(
            step_id=data["step_id"],
            description=data["description"],
            task=data["task"],
            language=data.get("language", "python"),
            output_variable=data.get("output_variable")
        )

class FileOperationStep(WorkflowStep):
    """ファイル操作ステップ"""
    
    def __init__(self, step_id: str, description: str, operation: str, 
                 file_path: str, content_variable: str = None):
        super().__init__(step_id, description)
        self.operation = operation  # read, write
        self.file_path = file_path
        self.content_variable = content_variable
        
    def execute(self, context: WorkflowContext) -> bool:
        """ファイル操作ステップを実行"""
        self.status = WorkflowStepStatus.IN_PROGRESS
        try:
            if self.operation == "read":
                # ファイルを読み込んでコンテキスト変数に保存
                with open(self.file_path, "r") as f:
                    content = f.read()
                if self.content_variable:
                    context.set_variable(self.content_variable, content)
                context.set_result(self.step_id, {
                    "content": content,
                    "file_path": self.file_path
                })
                self.result = {"content": content}
                
            elif self.operation == "write":
                # コンテキスト変数からコンテンツを取得してファイルに書き込み
                content = context.get_variable(self.content_variable)
                if content is None:
                    self.error = f"変数 '{self.content_variable}' が見つかりません"
                    self.status = WorkflowStepStatus.FAILED
                    return False
                    
                # ディレクトリがなければ作成
                Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)
                
                with open(self.file_path, "w") as f:
                    f.write(content)
                context.set_result(self.step_id, {
                    "file_path": self.file_path,
                    "success": True
                })
                self.result = {"file_path": self.file_path}
                
            else:
                self.error = f"未サポートのファイル操作: {self.operation}"
                self.status = WorkflowStepStatus.FAILED
                return False
                
            self.status = WorkflowStepStatus.COMPLETED
            return True
            
        except Exception as e:
            self.error = str(e)
            self.status = WorkflowStepStatus.FAILED
            return False
            
    def to_dict(self) -> Dict:
        """ステップをディクショナリに変換（オーバーライド）"""
        data = super().to_dict()
        data.update({
            "operation": self.operation,
            "file_path": self.file_path,
            "content_variable": self.content_variable
        })
        return data
        
    @classmethod
    def create_from_dict(cls, data: Dict) -> 'FileOperationStep':
        """ディクショナリからステップを作成"""
        return cls(
            step_id=data["step_id"],
            description=data["description"],
            operation=data["operation"],
            file_path=data["file_path"],
            content_variable=data.get("content_variable")
        )

# ステップタイプのレジストリ
STEP_TYPE_REGISTRY = {
    "CodeGenerationStep": CodeGenerationStep,
    "FileOperationStep": FileOperationStep
}

class WorkflowController:
    """AI制御ワークフローのコントローラークラス"""
    
    def __init__(self, goal: str, model_interface: Any):
        self.goal = goal
        self.model = model_interface
        self.steps: Dict[str, WorkflowStep] = {}
        self.context = WorkflowContext()
        self.step_order: List[str] = []
        
        # モデルインターフェースをコンテキストに設定
        self.context.set_variable("model_interface", model_interface)
        
    def add_step(self, step: WorkflowStep) -> None:
        """ワークフローにステップを追加"""
        self.steps[step.step_id] = step
        if step.step_id not in self.step_order:
            self.step_order.append(step.step_id)
            
    def execute(self) -> Dict[str, Any]:
        """ワークフローを実行"""
        results = {}
        for step_id in self.step_order:
            step = self.steps[step_id]
            logger.info(f"ステップ '{step_id}' を実行: {step.description}")
            
            success = step.execute(self.context)
            results[step_id] = {
                "success": success,
                "status": step.status.value,
                "result": step.result,
                "error": step.error
            }
            
            if not success:
                logger.error(f"ステップ '{step_id}' が失敗しました: {step.error}")
                break
                
        return results
        
    def to_dict(self) -> Dict:
        """ワークフローをディクショナリに変換"""
        return {
            "goal": self.goal,
            "steps": {step_id: step.to_dict() for step_id, step in self.steps.items()},
            "step_order": self.step_order
        }
        
    def to_json(self) -> str:
        """ワークフローをJSON文字列に変換"""
        return json.dumps(self.to_dict(), indent=2)
        
    def save_to_file(self, file_path: str) -> None:
        """ワークフローをJSONファイルに保存"""
        with open(file_path, "w") as f:
            f.write(self.to_json())
            
    @classmethod
    def from_dict(cls, data: Dict, model_interface: Any) -> 'WorkflowController':
        """ディクショナリからワークフローを作成"""
        controller = cls(data.get("goal", ""), model_interface)
        controller.step_order = data.get("step_order", [])
        
        for step_data in data.get("steps", {}).values():
            step = WorkflowStep.from_dict(step_data)
            controller.add_step(step)
            
        return controller
        
    @classmethod
    def load_from_file(cls, file_path: str, model_interface: Any) -> 'WorkflowController':
        """JSONファイルからワークフローを読み込み"""
        with open(file_path, "r") as f:
            data = json.load(f)
        return cls.from_dict(data, model_interface)


# JSONワークフロー定義のロード機能
def load_workflow_from_json(json_file: str, model_interface: Any) -> WorkflowController:
    """JSONファイルからワークフロー構造を読み込む"""
    return WorkflowController.load_from_file(json_file, model_interface)
