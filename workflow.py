"""
CLIコーディングアシスタント用のワークフロー機能
インタラクティブな編集と連続タスク処理をサポート
"""

import re
import json
import logging
from typing import Dict, List, Callable, Any, Optional
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class WorkflowStepType(Enum):
    """ワークフローステップの種類"""
    CODE_GENERATION = "code_generation"
    CODE_EDITING = "code_editing"
    CODE_REVIEW = "code_review"
    CODE_REFACTORING = "code_refactoring"
    TEST_GENERATION = "test_generation"
    DOCUMENTATION = "documentation"
    USER_INPUT = "user_input"
    FILE_OPERATION = "file_operation"
    CONDITIONAL = "conditional"
    LOOP = "loop"

@dataclass
class WorkflowStep:
    """ワークフローステップの定義"""
    step_type: WorkflowStepType
    description: str
    arguments: Dict[str, Any]
    condition: Optional[str] = None
    next_on_success: Optional[str] = None
    next_on_failure: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """ステップをディクショナリ形式に変換"""
        return {
            "step_type": self.step_type.value,
            "description": self.description,
            "arguments": self.arguments,
            "condition": self.condition,
            "next_on_success": self.next_on_success,
            "next_on_failure": self.next_on_failure
        }

class Workflow:
    """ワークフロー管理クラス"""
    
    def __init__(self, name: str, description: str, model_interface: Any):
        self.name = name
        self.description = description
        self.steps: Dict[str, WorkflowStep] = {}
        self.start_step: Optional[str] = None
        self.model_interface = model_interface
        self.results = {}
        self.interactive_mode = False
        
    def add_step(self, step_id: str, step: WorkflowStep) -> None:
        """ワークフローにステップを追加"""
        self.steps[step_id] = step
        if not self.start_step:
            self.start_step = step_id
    
    def set_interactive_mode(self, interactive: bool) -> None:
        """インタラクティブモードを設定"""
        self.interactive_mode = interactive
        
    def to_dict(self) -> Dict:
        """ワークフローをディクショナリに変換"""
        return {
            "name": self.name,
            "description": self.description,
            "steps": {k: v.to_dict() for k, v in self.steps.items()},
            "start_step": self.start_step
        }
    
    def from_dict(self, data: Dict) -> 'Workflow':
        """ディクショナリからワークフローを作成"""
        self.name = data["name"]
        self.description = data["description"]
        self.start_step = data.get("start_step")
        
        for step_id, step_data in data.get("steps", {}).items():
            step = WorkflowStep(
                step_type=WorkflowStepType(step_data["step_type"]),
                description=step_data["description"],
                arguments=step_data["arguments"],
                condition=step_data.get("condition"),
                next_on_success=step_data.get("next_on_success"),
                next_on_failure=step_data.get("next_on_failure")
            )
            self.steps[step_id] = step
            
        return self
        
    def save_to_file(self, filename: str) -> None:
        """ワークフローをJSONファイルに保存"""
        with open(filename, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
            
    @classmethod
    def load_from_file(cls, filename: str, model_interface: Any) -> 'Workflow':
        """JSONファイルからワークフローを読み込み"""
        with open(filename, "r") as f:
            data = json.load(f)
        return cls("", "", model_interface).from_dict(data)
    
    def execute(self, start_from: Optional[str] = None) -> Dict:
        """ワークフローを実行"""
        current_step_id = start_from or self.start_step
        if not current_step_id:
            raise ValueError("開始ステップが指定されていません")
            
        while current_step_id:
            if current_step_id not in self.steps:
                raise ValueError(f"ステップ '{current_step_id}' が見つかりません")
                
            current_step = self.steps[current_step_id]
            logger.info(f"ステップ '{current_step_id}' を実行: {current_step.description}")
            
            # 条件チェック
            if current_step.condition and not self._evaluate_condition(current_step.condition):
                logger.info(f"条件 '{current_step.condition}' が満たされませんでした。スキップします")
                current_step_id = current_step.next_on_failure
                continue
                
            # ステップのタイプに応じた実行
            try:
                result = self._execute_step(current_step)
                self.results[current_step_id] = result
                
                # インタラクティブモードでユーザーの確認
                if self.interactive_mode and current_step.step_type != WorkflowStepType.USER_INPUT:
                    if not self._get_user_confirmation(result, current_step_id):
                        logger.info("ユーザーがステップ結果を却下しました")
                        return self.results
                
                current_step_id = current_step.next_on_success
            except Exception as e:
                logger.error(f"ステップ実行中にエラー: {str(e)}")
                self.results[current_step_id] = {"error": str(e)}
                current_step_id = current_step.next_on_failure
                
        return self.results
    
    def _execute_step(self, step: WorkflowStep) -> Dict:
        """個々のステップを実行"""
        # ステップタイプごとの処理ロジック
        if step.step_type == WorkflowStepType.USER_INPUT:
            prompt = step.arguments.get("prompt", "入力してください: ")
            user_input = input(prompt)
            return {"input": user_input}
            
        elif step.step_type == WorkflowStepType.CODE_GENERATION:
            # モデルインターフェースを使用してコード生成
            task = step.arguments.get("task", "")
            prompt = f"Pythonで{task}を実装するコードを生成してください。"
            response = self.model_interface.generate_content(prompt).text.strip()
            code_match = re.search(r"```python\n(.*?)\n```", response, re.DOTALL)
            if code_match:
                code = code_match.group(1).strip()
            else:
                code = response
            return {"code": code, "full_response": response}
            
        elif step.step_type == WorkflowStepType.CODE_EDITING:
            filename = step.arguments.get("filename")
            instruction = step.arguments.get("instruction", "")
            
            # ファイルがあれば読み込む
            if filename:
                try:
                    with open(filename, "r") as f:
                        code = f.read()
                except FileNotFoundError:
                    return {"error": f"ファイル {filename} が見つかりません"}
            else:
                # 前のステップの結果からコードを取得
                prev_step_id = step.arguments.get("previous_step")
                if prev_step_id and prev_step_id in self.results:
                    code = self.results[prev_step_id].get("code", "")
                else:
                    return {"error": "編集するコードが指定されていません"}
            
            # モデルを使ってコード編集
            prompt = f"以下のPythonコードを編集してください。指示: {instruction}\nコード:\n{code}"
            response = self.model_interface.generate_content(prompt).text.strip()
            
            code_match = re.search(r"```python\n(.*?)\n```", response, re.DOTALL)
            if code_match:
                edited_code = code_match.group(1).strip()
            else:
                edited_code = response
                
            # ファイルがあれば保存
            if filename and step.arguments.get("save", False):
                with open(filename, "w") as f:
                    f.write(edited_code)
            
            return {"code": edited_code, "original_code": code, "full_response": response}
            
        elif step.step_type == WorkflowStepType.FILE_OPERATION:
            operation = step.arguments.get("operation")
            filename = step.arguments.get("filename")
            
            if not filename:
                return {"error": "ファイル名が指定されていません"}
                
            if operation == "read":
                try:
                    with open(filename, "r") as f:
                        content = f.read()
                    return {"content": content}
                except Exception as e:
                    return {"error": f"ファイル読み込みエラー: {str(e)}"}
                    
            elif operation == "write":
                content = step.arguments.get("content")
                # 前のステップの結果からコンテンツを取得
                if not content:
                    prev_step_id = step.arguments.get("previous_step")
                    if prev_step_id and prev_step_id in self.results:
                        content = self.results[prev_step_id].get("code", "")
                
                try:
                    with open(filename, "w") as f:
                        f.write(content)
                    return {"filename": filename, "success": True}
                except Exception as e:
                    return {"error": f"ファイル書き込みエラー: {str(e)}"}
            else:
                return {"error": f"未サポートのファイル操作: {operation}"}
                
        # その他のステップタイプも同様に実装...
        
        return {"warning": f"ステップタイプ {step.step_type} の実装が完了していません"}
    
    def _evaluate_condition(self, condition: str) -> bool:
        """条件式を評価"""
        # 簡易的な条件評価の例
        # 実際には安全なエバリュエータを実装する
        try:
            # {step_id.result_key} 形式の参照を解決
            pattern = r'\{([^}]+)\.([^}]+)\}'
            
            def replace_var(match):
                step_id, key = match.groups()
                if step_id in self.results and key in self.results[step_id]:
                    return repr(self.results[step_id][key])
                return "None"
                
            eval_condition = re.sub(pattern, replace_var, condition)
            return bool(eval(eval_condition))
        except Exception as e:
            logger.error(f"条件評価エラー: {str(e)}")
            return False
    
    def _get_user_confirmation(self, result: Dict, step_id: str) -> bool:
        """ユーザーに結果の確認を求める"""
        print(f"\n==== ステップ '{step_id}' の結果 ====")
        
        # コードを含む場合は表示
        if "code" in result:
            print("\n```python")
            print(result["code"])
            print("```\n")
        elif "content" in result:
            print("\nコンテンツ:")
            print(result["content"])
        
        # エラーがあれば表示
        if "error" in result:
            print(f"\nエラー: {result['error']}")
        
        while True:
            response = input("\nこの結果を承認しますか？ (y/n/e - 'e'は編集): ").lower()
            if response == 'y':
                return True
            elif response == 'n':
                return False
            elif response == 'e':
                # インタラクティブな編集
                if "code" in result:
                    print("\n現在のコード:")
                    print(result["code"])
                    print("\n編集したコードを入力してください（終了は 'END' のみの行）:")
                    
                    lines = []
                    while True:
                        line = input()
                        if line == "END":
                            break
                        lines.append(line)
                    
                    new_code = "\n".join(lines)
                    if new_code:
                        result["code"] = new_code
                        return True
            else:
                print("'y', 'n', または 'e' で回答してください。")

def create_workflow_from_prompt(prompt: str, model_interface: Any) -> Workflow:
    """プロンプトからワークフローを作成"""
    # モデルにワークフロー生成を依頼
    workflow_prompt = f"""
    以下のタスクに基づいて、ワークフローをJSON形式で生成してください:
    {prompt}
    
    次の形式に従ってください:
    {{
      "name": "ワークフロー名",
      "description": "ワークフローの詳細説明",
      "start_step": "最初のステップID",
      "steps": {{
        "step_id_1": {{
          "step_type": "ステップタイプ",
          "description": "ステップの説明",
          "arguments": {{
            // ステップに必要な引数
          }},
          "next_on_success": "次のステップID",
          "next_on_failure": "失敗時の次のステップID"
        }},
        // 他のステップ...
      }}
    }}
    
    利用可能なステップタイプ:
    - code_generation: コード生成
    - code_editing: コード編集
    - code_review: コードレビュー
    - code_refactoring: リファクタリング
    - test_generation: テスト生成
    - documentation: ドキュメント生成
    - user_input: ユーザー入力
    - file_operation: ファイル操作
    - conditional: 条件分岐
    - loop: ループ処理
    """
    
    response = model_interface.generate_content(workflow_prompt).text.strip()
    
    # JSONを抽出
    json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_match = re.search(r'(\{.*\})', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            raise ValueError("JSONワークフローが見つかりませんでした")
            
    workflow_data = json.loads(json_str)
    return Workflow("", "", model_interface).from_dict(workflow_data)