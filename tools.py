"""
CLI AI アシスタント用のツール機能モジュール
"""

import os
import re
import difflib
import logging
from pathlib import Path
from typing import Dict, Optional, Callable, Any

import google.generativeai as genai

logger = logging.getLogger(__name__)

def clean_code_output(code_text: str) -> str:
    """コードブロックからコードを抽出する"""
    # 複数のコードブロックがある場合の対応
    if code_text.startswith("```python") and "```python" in code_text[10:]:
        match = re.search(r"```python\s*(.*?)\s*```", code_text, re.DOTALL)
        if match:
            return match.group(1).strip()
    
    # 通常のコードブロック
    match = re.search(r"```(?:python)?\s*(.*?)\s*```", code_text, re.DOTALL)
    if match:
        return match.group(1).strip()
        
    return code_text

def format_response(result_type: str, content: str, is_code: bool = False) -> str:
    """統一された出力フォーマット"""
    prefix = f"Result: {result_type}"
    if is_code:
        return f"{prefix}\n```python\n{content}\n```"
    return f"{prefix}\n{content}"

def extract_filename_from_prompt(prompt: str) -> Optional[str]:
    """プロンプトからファイル名を抽出する"""
    # ファイル名のパターンを探す
    patterns = [
        r'(\w+\.py)を読み込んで',     # 日本語パターン: "xxx.pyを読み込んで"
        r'edit\s+(\w+\.py)',          # 英語パターン: "edit xxx.py"
        r'ファイル[名は]?[：:]?\s*[「『]?(\w+\.py)[」』]?', # "ファイル名：xxx.py"
        r'(\w+\.py)',                 # 単純にファイル名だけのパターン
    ]
    
    for pattern in patterns:
        match = re.search(pattern, prompt)
        if match:
            return match.group(1)
    
    return None

def process_code_tool(func_name: str, args: Dict, prompt: str, 
                      api_call_func: Callable[[str], str], is_code: bool = False,
                      get_most_recent_code_func: Callable[[], Optional[str]] = None) -> str:
    """共通のコード処理パターン"""
    code = args.get("code") or (get_most_recent_code_func() if get_most_recent_code_func else None)
    if not code:
        return format_response("Error", f"{func_name}するコードが見つかりませんでした。")
        
    response = api_call_func(code)
    
    if is_code:
        clean_response = clean_code_output(response)
        return format_response(func_name.capitalize(), clean_response, is_code=True)
        
    return format_response(func_name.capitalize(), response)

def handle_generate_code(args: Dict, prompt: str, model: Any) -> str:
    """コード生成処理"""
    task = args.get("task", args.get("description", prompt))
    
    code_prompt = f"Pythonで{task}を実装するコードだけを生成してください。説明、コメント、コードブロック（```）は一切不要です。"
    raw_code_response = model.generate_content(code_prompt).text.strip()
    clean_code = clean_code_output(raw_code_response)
    return format_response("Generated Code", clean_code, is_code=True)

def handle_save_code(args: Dict, get_most_recent_code_func: Callable[[], Optional[str]]) -> str:
    """コード保存処理"""
    code = args.get("code") or (get_most_recent_code_func() if get_most_recent_code_func else None)
    if not code:
        return format_response("Error", "保存するコードが見つかりませんでした。")
        
    filename = args.get("filename", "output.py")
    
    try:
        with open(filename, "w") as f:
            f.write(code)
        return format_response("Saved", f"コードを {filename} に保存しました。")
        
    except Exception as e:
        return format_response("Error", f"コードの保存中にエラーが発生しました: {str(e)}")

def handle_edit_code(args: Dict, prompt: str, model: Any) -> str:
    """コード編集処理 - 堅牢性を向上"""
    # ファイル名を取得 - 複数のキーをサポート
    filename = args.get("filename") or args.get("filepath")
    if not filename:
        filename = extract_filename_from_prompt(prompt)
    
    if not filename:
        return format_response("Error", "編集するファイル名が指定されていません。")
    
    # ファイルの存在と権限チェック
    file_path = Path(filename)
    if not file_path.exists():
        return format_response("Error", f"{filename} が見つかりませんでした。")
    if not os.access(file_path, os.R_OK):
        return format_response("Error", f"{filename} を読み取る権限がありません。")
    if not os.access(file_path, os.W_OK):
        return format_response("Error", f"{filename} を書き込む権限がありません。")
    
    try:
        # コードを読み込み
        with open(file_path, "r") as f:
            original_code = f.read()
            
        # 直接コードが提供されているか確認
        new_code = args.get("code")
        if new_code and isinstance(new_code, str):
            # コードが提供されている場合は直接それを使用
            clean_code = clean_code_output(new_code)
        else:
            # 編集指示の取得 - 複数のキーをサポート
            edit_instruction = args.get("instruction") or args.get("instructions") or prompt
            
            # 新しいコードを生成
            edit_prompt = f"以下のPythonコードを編集してください。指示: {edit_instruction}\nコード:\n{original_code}"
            edited_code = model.generate_content(edit_prompt).text.strip()
            clean_code = clean_code_output(edited_code)
        
        # 変更前のコードと編集後のコードを比較
        diff = list(difflib.unified_diff(
            original_code.splitlines(), 
            clean_code.splitlines(),
            fromfile=f"修正前: {filename}",
            tofile=f"修正後: {filename}",
            lineterm=''
        ))
        diff_text = '\n'.join(diff) if diff else "変更はありませんでした。"
        
        # 新しいコードを書き込み
        with open(file_path, "w") as f:
            f.write(clean_code)
        
        # 応答を作成
        formatted_response = format_response("Edited", clean_code, is_code=True)
        formatted_response += f"\n\nDiff:\n```diff\n{diff_text}\n```"
        
        return formatted_response
        
    except Exception as e:
        logger.error(f"ファイル編集エラー: {str(e)}")
        return format_response("Error", f"ファイル編集中にエラーが発生しました: {str(e)}")
