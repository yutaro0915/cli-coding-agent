import google.generativeai as genai
import argparse
import os
import sys
import json
import re
import time
import uuid
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

# 独自モジュールのインポート
from tools import (
    clean_code_output, format_response, extract_filename_from_prompt,
    process_code_tool, handle_generate_code, handle_save_code, handle_edit_code
)
from workflow import (
    Workflow, WorkflowStep, WorkflowStepType, create_workflow_from_prompt
)

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 設定値
DEFAULT_MAX_TOKENS = 500
DEFAULT_CONTEXT_LENGTH = 10
DEFAULT_MODEL = "gemini-2.0-flash"

class CLIAssistant:
    """CLI AI コーディングアシスタント"""
    
    def __init__(self, max_tokens: int = DEFAULT_MAX_TOKENS, 
                 context_length: int = DEFAULT_CONTEXT_LENGTH,
                 model: str = DEFAULT_MODEL):
        # APIキー設定
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            logger.error("GOOGLE_API_KEYの環境変数が設定されていません。")
            logger.info("以下のコマンドを実行してAPIキーを設定してください:")
            logger.info("export GOOGLE_API_KEY='あなたのGoogle APIキー'")
            sys.exit(1)
            
        genai.configure(api_key=self.api_key)
        
        self.max_tokens = max_tokens
        self.context_length = context_length
        self.model = genai.GenerativeModel(model)
        
        # 会話履歴の初期化
        self.conversation_history = [
            {"role": "user", "parts": ["""あなたはCLIコーディングアシスタントです。ユーザーの入力に基づいて、適切なツールを選択して実行してください。利用可能なツールは以下の通りです：

1. generate_code: Pythonコードを生成します。説明やコメントは含めず、コードだけを返します。
2. review_code: Pythonコードをレビューし、改善点を提案。
3. debug_code: Pythonコードの潜在的なバグを指摘。
4. save_code: 生成したコードをファイルに保存。
5. edit_code: 既存コードを読み込んで編集。
6. test_code: コード用のテストを生成。
7. explain_code: コードの動作を説明。
8. refactor_code: コードをリファクタリング。
9. generate_docs: コードのドキュメントを生成。

ユーザーの意図を理解し、適切なツールを選択してください。ツールを呼び出す際は、以下の形式でJSONを返してください：
{"function": "ツール名", "arguments": {"引数名": "値"}}

JSONだけを返し、マークダウンのコードブロックで囲まないでください。"""]}
        ]
        
        # 一時ファイルディレクトリ
        self.temp_dir = Path("temp_files")
        self.temp_dir.mkdir(exist_ok=True)
        
    def safe_api_call(self, call_func, max_retries: int = 3, retry_delay: int = 2) -> Any:
        """API呼び出しを安全に行う（リトライロジック付き）"""
        for attempt in range(max_retries):
            try:
                return call_func()
            except Exception as e:
                if "Resource has been exhausted" in str(e) or "429" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        logger.warning(f"API制限に達しました。{wait_time}秒待機してリトライします...")
                        time.sleep(wait_time)
                    else:
                        logger.error("APIリクエスト制限に達しました。しばらく待ってから再試行してください。")
                        raise
                else:
                    logger.error(f"エラーが発生しました: {e}")
                    raise
    
    def get_most_recent_code(self) -> Optional[str]:
        """最新のコードを会話履歴から取得する"""
        for message in reversed(self.conversation_history):
            if message.get("role") == "model":
                content = message.get("parts", [""])[0]
                if "```python" in content:
                    try:
                        code = content.split("```python\n")[1].split("\n```")[0].strip()
                        return code
                    except IndexError:
                        pass
                    
                # Result: Generated Code などのフォーマットからも抽出
                match = re.search(r"Result: .*?\n```python\n(.*?)\n```", content, re.DOTALL)
                if match:
                    return match.group(1).strip()
        return None
    
    def create_workflow(self, task_description: str) -> Workflow:
        """タスク記述からワークフローを作成"""
        return create_workflow_from_prompt(task_description, self.model)
        
    def execute_workflow(self, workflow: Workflow, interactive: bool = True) -> Dict:
        """ワークフローを実行"""
        workflow.set_interactive_mode(interactive)
        return workflow.execute()
        
    def save_workflow(self, workflow: Workflow, filename: str) -> None:
        """ワークフローを保存"""
        workflow.save_to_file(filename)
        
    def load_workflow(self, filename: str) -> Workflow:
        """保存されたワークフローを読み込む"""
        return Workflow.load_from_file(filename, self.model)
        
    def chat_with_gemini(self, prompt: str) -> str:
        """GeminiとのChat形式での対話"""
        # 会話履歴に追加
        self.conversation_history.append({"role": "user", "parts": [prompt]})
        
        # 会話履歴をコンテキスト長に制限
        if len(self.conversation_history) > self.context_length:
            self.conversation_history[:] = self.conversation_history[-self.context_length:]
    
        # Geminiからレスポンスを生成
        def generate_response():
            return self.model.generate_content(
                self.conversation_history,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=self.max_tokens
                )
            )
    
        response = self.safe_api_call(generate_response)
        assistant_response = response.text.strip()
        
        # JSON応答の抽出 - 複数のパターンに対応
        json_match = re.search(r'```(?:json)?\s*(.*?)```', assistant_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # JSON形式でない場合、またはブロック外にある場合を処理
            # 単純なJSONオブジェクトを検出する正規表現
            json_match = re.search(r'(\{.*\})', assistant_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                json_str = assistant_response
        
        try:
            # JSON解析とツール呼び出し
            tool_call = json.loads(json_str)
            # JSONの構造検証を追加
            if not isinstance(tool_call, dict):
                raise TypeError("JSON response is not a dictionary")
                
            if "function" in tool_call and "arguments" in tool_call:
                func_name = tool_call["function"]
                args = tool_call["arguments"]
                
                # 各ツール関数の処理
                if func_name == "generate_code":
                    formatted_response = self.safe_api_call(
                        lambda: handle_generate_code(args, prompt, self.model)
                    )
                
                elif func_name == "review_code":
                    formatted_response = self.safe_api_call(
                        lambda: process_code_tool("review", args, prompt, 
                            lambda code: self.model.generate_content(
                                f"以下のPythonコードをレビューして、改善点や提案を自然言語で教えてください:\n{code}"
                            ).text.strip(),
                            get_most_recent_code_func=self.get_most_recent_code
                        )
                    )
                
                elif func_name == "debug_code":
                    formatted_response = self.safe_api_call(
                        lambda: process_code_tool("debug", args, prompt, 
                            lambda code: self.model.generate_content(
                                f"以下のPythonコードをデバッグして、潜在的なバグや問題点を自然言語で教えてください:\n{code}"
                            ).text.strip(),
                            get_most_recent_code_func=self.get_most_recent_code
                        )
                    )
                
                elif func_name == "save_code":
                    formatted_response = handle_save_code(args, self.get_most_recent_code)
                
                elif func_name == "edit_code":
                    formatted_response = self.safe_api_call(
                        lambda: handle_edit_code(args, prompt, self.model)
                    )
                
                elif func_name == "test_code":
                    formatted_response = self.safe_api_call(
                        lambda: process_code_tool("test", args, prompt, 
                            lambda code: self.model.generate_content(
                                f"以下のPythonコード用のテストコードを生成してください:\n{code}"
                            ).text.strip(), 
                            is_code=True,
                            get_most_recent_code_func=self.get_most_recent_code
                        )
                    )
                
                elif func_name == "explain_code":
                    formatted_response = self.safe_api_call(
                        lambda: process_code_tool("explain", args, prompt, 
                            lambda code: self.model.generate_content(
                                f"以下のPythonコードの動作を自然言語で説明してください:\n{code}"
                            ).text.strip(),
                            get_most_recent_code_func=self.get_most_recent_code
                        )
                    )
                
                elif func_name == "refactor_code":
                    formatted_response = self.safe_api_call(
                        lambda: process_code_tool("refactor", args, prompt, 
                            lambda code: self.model.generate_content(
                                f"以下のPythonコードをリファクタリングしてください。より簡潔で効率的なコードにしてください:\n{code}"
                            ).text.strip(),
                            is_code=True,
                            get_most_recent_code_func=self.get_most_recent_code
                        )
                    )
                
                elif func_name == "generate_docs":
                    formatted_response = self.safe_api_call(
                        lambda: process_code_tool("documentation", args, prompt, 
                            lambda code: self.model.generate_content(
                                f"以下のPythonコードにドキュメント文字列（docstring）とコメントを追加してください:\n{code}"
                            ).text.strip(),
                            is_code=True,
                            get_most_recent_code_func=self.get_most_recent_code
                        )
                    )
                
                elif func_name == "run_code":
                    formatted_response = format_response("Error", "コード実行機能は現在利用できません。IDEの実行機能をご利用ください。")
                
                # ワークフロー関連の機能を追加
                elif func_name == "create_workflow":
                    task = args.get("task", prompt)
                    try:
                        workflow = self.create_workflow(task)
                        workflow_name = args.get("name", f"workflow_{int(time.time())}")
                        
                        # ワークフローを保存
                        filename = args.get("filename", f"{workflow_name}.json")
                        self.save_workflow(workflow, filename)
                        
                        formatted_response = format_response(
                            "Workflow Created", 
                            f"ワークフロー '{workflow.name}' を作成し、{filename} に保存しました。\n"
                            f"説明: {workflow.description}\n"
                            f"ステップ数: {len(workflow.steps)}"
                        )
                    except Exception as e:
                        formatted_response = format_response(
                            "Error", 
                            f"ワークフロー作成中にエラーが発生しました: {str(e)}"
                        )
                
                elif func_name == "execute_workflow":
                    filename = args.get("filename")
                    if not filename:
                        formatted_response = format_response(
                            "Error", 
                            "実行するワークフローのファイル名が指定されていません。"
                        )
                    else:
                        try:
                            workflow = self.load_workflow(filename)
                            interactive = args.get("interactive", True)
                            results = self.execute_workflow(workflow, interactive)
                            
                            # 結果の要約
                            result_summary = "\n".join(f"- {step_id}: {'成功' if 'error' not in result else '失敗: '+result['error']}" 
                                                for step_id, result in results.items())
                            
                            formatted_response = format_response(
                                "Workflow Executed", 
                                f"ワークフロー '{workflow.name}' を実行しました。\n結果概要:\n{result_summary}"
                            )
                        except Exception as e:
                            formatted_response = format_response(
                                "Error", 
                                f"ワークフロー実行中にエラーが発生しました: {str(e)}"
                            )
                
                else:
                    formatted_response = format_response("Error", f"不明な関数名 '{func_name}' です。")
                
                # 会話履歴に応答を追加
                self.conversation_history.append({"role": "model", "parts": [formatted_response]})
                return formatted_response
                
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析エラー: {e}. 通常の応答として処理します。")
            self.conversation_history.append({"role": "model", "parts": [assistant_response]})
            return assistant_response
        except Exception as e:
            logger.error(f"ツール呼び出しエラー: {e}")
            error_response = format_response("Error", f"ツール呼び出し中にエラーが発生しました: {str(e)}")
            self.conversation_history.append({"role": "model", "parts": [error_response]})
            return error_response
        
        # デフォルトの応答
        self.conversation_history.append({"role": "model", "parts": [assistant_response]})
        return assistant_response
    
    def run_cli(self):
        """CLIインターフェースを実行"""
        logger.info("CLI AI エージェントへようこそ。終了するには 'exit' または 'quit' と入力してください。")
        
        while True:
            try:
                user_input = input("User> ")
                if user_input.lower() in ["exit", "quit"]:
                    logger.info("エージェントを終了します。")
                    break
                    
                response = self.chat_with_gemini(user_input)
                print(response)
                
            except KeyboardInterrupt:
                logger.info("\nエージェントを終了します。")
                break
                
            except Exception as e:
                logger.error(f"エラーが発生しました: {str(e)}")
                logger.info("もう一度試すか、別のコマンドを入力してください。")
    
    def cleanup(self):
        """一時ファイルの削除などのクリーンアップ処理 - 改善版"""
        try:
            if self.temp_dir.exists():
                logger.info(f"一時ディレクトリ {self.temp_dir} のクリーンアップを実行中...")
                # 一時ディレクトリ内のファイルを削除
                for file in self.temp_dir.glob("*"):
                    try:
                        if file.is_file():
                            logger.debug(f"一時ファイル {file} を削除中...")
                            file.unlink(missing_ok=True)
                    except Exception as e:
                        logger.warning(f"ファイル {file} の削除中にエラー: {str(e)}")
                
                # 一時ディレクトリを削除
                try:
                    self.temp_dir.rmdir()
                    logger.info(f"一時ディレクトリ {self.temp_dir} を削除しました")
                except OSError as e:
                    logger.warning(f"一時ディレクトリの削除に失敗: {str(e)}")
                    # 強制的に削除を試みる
                    try:
                        shutil.rmtree(self.temp_dir, ignore_errors=True)
                        logger.info("一時ディレクトリを強制的に削除しました")
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"クリーンアップ中にエラーが発生しました: {str(e)}")
            
        # 作業ディレクトリに残っているかもしれないtemp*.pyファイルもチェック
        try:
            for temp_file in Path(".").glob("temp*.py"):
                try:
                    temp_file.unlink(missing_ok=True)
                    logger.debug(f"残留一時ファイル {temp_file} を削除しました")
                except Exception:
                    pass
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(description="CLI AI エージェント")
    parser.add_argument('--max_tokens', type=int, default=DEFAULT_MAX_TOKENS, help="出力の最大トークン数")
    parser.add_argument('--context_length', type=int, default=DEFAULT_CONTEXT_LENGTH, help="保存する会話の最大数")
    parser.add_argument('--model', type=str, default=DEFAULT_MODEL, help="使用するGeminiモデル")
    parser.add_argument('--task', type=str, help="タスクを指定（例: コード生成）")
    parser.add_argument('--file', type=str, help="対象ファイル")
    parser.add_argument('--log_level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default='INFO', 
                        help="ログレベルを設定")
    parser.add_argument('--workflow', type=str, help="実行するワークフローファイル")
    parser.add_argument('--non-interactive', action='store_true', help="ワークフローを対話なしで実行")
    args = parser.parse_args()
    
    # ログレベルを設定
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # アシスタントの作成
    assistant = CLIAssistant(
        max_tokens=args.max_tokens,
        context_length=args.context_length,
        model=args.model
    )
    
    
    try:
        # ワークフローが指定された場合
        if args.workflow:
            workflow_path = args.workflow
            if not os.path.exists(workflow_path):
                logger.error(f"指定されたワークフローファイル {workflow_path} が見つかりません")
                sys.exit(1)
            
            workflow = assistant.load_workflow(workflow_path)
            logger.info(f"ワークフロー '{workflow.name}' を読み込みました")
            results = assistant.execute_workflow(workflow, not args.non_interactive)
            
            # 結果の要約表示
            print("\n=== ワークフロー実行結果 ===")
            for step_id, result in results.items():
                if "error" in result:
                    status = f"失敗: {result['error']}"
                else:
                    status = "成功"
                print(f"- {step_id}: {status}")
        
        # 特定のタスクが指定された場合の処理
        elif args.task == "コード生成" and args.file:
            prompt = f"Pythonで便利な関数を生成して{args.file}に保存してください。"
            response = assistant.chat_with_gemini(prompt)
            try:
                code_match = re.search(r"```python\n(.*?)\n```", response, re.DOTALL)
                if (code_match):
                    code = code_match.group(1).strip()
                    with open(args.file, 'w') as f:
                        f.write(code)
                    print(response)
                    logger.info(f"コードを {args.file} に保存しました。")
                else:
                    raise IndexError("コードブロックが見つかりません")
            except IndexError as e:
                logger.error(f"コードの抽出に失敗しました: {str(e)}")
                print(response)
        else:
            # インタラクティブモード
            assistant.run_cli()
    finally:
        # クリーンアップ処理
        assistant.cleanup()

if __name__ == '__main__':
    main()