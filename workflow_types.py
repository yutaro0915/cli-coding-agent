"""
AI制御ワークフロー用のステップタイプ定義
拡張可能なステップタイプのセットを提供
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

@dataclass
class StepDefinition:
    """ステップ定義のデータクラス"""
    type: str
    description: str
    parameters: Dict[str, Any]
    completion_criteria: Optional[List[str]] = None
    importance: int = 1  # 重要度 (1-5)

class DependencyType(Enum):
    """タスク間の依存関係タイプ"""
    DATA = "data"         # データ依存関係
    SEQUENCE = "sequence"  # 順序依存関係
    CONDITION = "condition"  # 条件依存関係

@dataclass
class TaskDependency:
    """タスク間の依存関係定義"""
    source_task_id: str
    target_task_id: str
    dependency_type: DependencyType
    data_mapping: Optional[Dict[str, str]] = None  # ソースの出力→ターゲットの入力へのマッピング
    condition: Optional[str] = None  # 条件式（条件依存関係の場合）

class StepType(Enum):
    """AI制御ワークフローで使用可能なステップタイプ"""
    CODE_GENERATION = "code_generation"
    CODE_EDITING = "code_editing"
    CODE_REVIEW = "code_review"
    TEST_GENERATION = "test_generation"
    FILE_OPERATION = "file_operation"
    DEPENDENCY_INSTALLATION = "dependency_installation"
    DOCUMENTATION = "documentation"
    USER_APPROVAL = "user_approval"
    CONDITIONAL = "conditional"
    LOOP = "loop"
    ERROR_HANDLER = "error_handler"
    EVALUATION = "evaluation"
    
    @classmethod
    def get_required_params(cls, step_type: 'StepType') -> List[str]:
        """ステップタイプに必要なパラメータのリストを返す"""
        params_map = {
            cls.CODE_GENERATION: ["task", "language"],
            cls.CODE_EDITING: ["source_file", "instructions"],
            cls.CODE_REVIEW: ["target_file", "review_focus"],
            cls.TEST_GENERATION: ["source_file", "test_framework"],
            cls.FILE_OPERATION: ["operation", "file_path"],
            cls.DEPENDENCY_INSTALLATION: ["dependencies"],
            cls.DOCUMENTATION: ["target", "doc_type"],
            cls.USER_APPROVAL: ["approval_message", "options"],
            cls.CONDITIONAL: ["condition"],
            cls.LOOP: ["iteration_variable", "condition"],
            cls.ERROR_HANDLER: ["handled_exceptions", "recovery_action"],
            cls.EVALUATION: ["target", "criteria"]
        }
        return params_map.get(step_type, [])

# ステップタイプごとの実行関数の型定義
StepExecutorFunction = Callable[[Dict[str, Any], Any], Dict[str, Any]]

class StepTypeRegistry:
    """ステップタイプとその実行関数のレジストリ"""
    
    def __init__(self):
        self.executors: Dict[StepType, StepExecutorFunction] = {}
        
    def register(self, step_type: StepType, executor: StepExecutorFunction) -> None:
        """ステップタイプにエクゼキュータを登録"""
        self.executors[step_type] = executor
        
    def get_executor(self, step_type: StepType) -> Optional[StepExecutorFunction]:
        """ステップタイプのエクゼキュータを取得"""
        return self.executors.get(step_type)
        
    def execute_step(self, step_type: StepType, params: Dict[str, Any], 
                     model_interface: Any) -> Dict[str, Any]:
        """指定されたステップタイプを実行"""
        executor = self.get_executor(step_type)
        if not executor:
            raise ValueError(f"ステップタイプ {step_type.value} の実行関数が登録されていません")
            
        return executor(params, model_interface)

# グローバルなレジストリインスタンス
STEP_REGISTRY = StepTypeRegistry()
