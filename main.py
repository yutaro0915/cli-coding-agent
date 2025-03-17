import google.generativeai as genai
import argparse
import os
import sys
import json
import re
import subprocess
import time

# APIキー設定
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("エラー: GOOGLE_API_KEYの環境変数が設定されていません。")
    print("以下のコマンドを実行してAPIキーを設定してください:")
    print("export GOOGLE_API_KEY='あなたのGoogle APIキー'")
    sys.exit(1)

genai.configure(api_key=api_key)

MAX_TOKENS = 500
CONTEXT_LENGTH = 10
conversation_history = [
    {"role": "user", "parts": ["""あなたはCLIコーディングアシスタントです。ユーザーの入力に基づいて、適切なツールを選択して実行してください。利用可能なツールは以下の通りです：

1. generate_code: Pythonコードを生成します。説明やコメントは含めず、コードだけを返します。
2. review_code: Pythonコードをレビューし、改善点を提案。
3. run_code: Pythonコードを実行し、結果を返す。
4. debug_code: Pythonコードの潜在的なバグを指摘。
5. save_code: 生成したコードをファイルに保存。
6. edit_code: 既存コードを読み込んで編集。
7. test_code: コード用のテストを生成。
8. explain_code: コードの動作を説明。

ユーザーの意図を理解し、適切なツールを選択してください。ツールを呼び出す際は、以下の形式でJSONを返してください：
{"function": "ツール名", "arguments": {"引数名": "値"}}

JSONだけを返し、マークダウンのコードブロックで囲まないでください。"""]}
]

model = genai.GenerativeModel("gemini-2.0-flash")

def safe_api_call(call_func, max_retries=3, retry_delay=2):
    for attempt in range(max_retries):
        try:
            return call_func()
        except Exception as e:
            if "Resource has been exhausted" in str(e) or "429" in str(e):
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"API制限に達しました。{wait_time}秒待機してリトライします...")
                    time.sleep(wait_time)
                else:
                    print("APIリクエスト制限に達しました。しばらく待ってから再試行してください。")
                    raise
            else:
                print(f"エラーが発生しました: {e}")
                raise

def clean_code_output(code_text):
    if code_text.startswith("```python") and "```python" in code_text[10:]:
        match = re.search(r"```python\s*(.*?)\s*```", code_text, re.DOTALL)
        if match:
            return match.group(1).strip()
    match = re.search(r"```(?:python)?\s*(.*?)\s*```", code_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return code_text

def get_most_recent_code():
    for message in reversed(conversation_history):
        if message.get("role") == "model":
            content = message.get("parts", [""])[0]
            if "```python" in content:
                try:
                    code = content.split("```python\n")[1].split("\n```")[0].strip()
                    return code
                except IndexError:
                    pass
    return None

def format_response(result_type, content, is_code=False):
    """統一された出力フォーマット"""
    prefix = f"Result: {result_type}"
    if is_code:
        return f"{prefix}\n```python\n{content}\n```"
    return f"{prefix}\n{content}"

def process_code_tool(func_name, args, prompt, api_call_func, is_code=False):
    """共通のコード処理パターン"""
    code = args.get("code") or get_most_recent_code()
    if not code:
        return format_response("Error", f"{func_name}するコードが見つかりませんでした。")
    response = safe_api_call(lambda: api_call_func(code))
    if is_code:
        clean_response = clean_code_output(response)
        return format_response(func_name.capitalize(), clean_response, is_code=True)
    return format_response(func_name.capitalize(), response)

def extract_filename_from_prompt(prompt):
    """プロンプトからファイル名を抽出する"""
    # ファイル名のパターンを探す
    patterns = [
        r'(\w+\.py)を読み込んで',  # 日本語パターン: "xxx.pyを読み込んで"
        r'edit\s+(\w+\.py)',       # 英語パターン: "edit xxx.py"
        r'(\w+\.py)',              # 単純にファイル名だけのパターン
    ]
    
    for pattern in patterns:
        match = re.search(pattern, prompt)
        if match:
            return match.group(1)
    
    return None

def chat_with_gemini(prompt):
    global conversation_history, CONTEXT_LENGTH, MAX_TOKENS
    
    conversation_history.append({"role": "user", "parts": [prompt]})
    if len(conversation_history) > CONTEXT_LENGTH:
        conversation_history[:] = conversation_history[-CONTEXT_LENGTH:]

    def generate_response():
        return model.generate_content(
            conversation_history,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=MAX_TOKENS
            )
        )

    response = safe_api_call(generate_response)
    assistant_response = response.text.strip()
    
    json_match = re.search(r'```(?:json)?\s*(.*?)```', assistant_response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        json_str = assistant_response
    
    try:
        tool_call = json.loads(json_str)
        if "function" in tool_call and "arguments" in tool_call:
            func_name = tool_call["function"]
            args = tool_call["arguments"]
            
            if func_name == "generate_code":
                task = args.get("task", args.get("description", prompt))
                def generate_code_response():
                    code_prompt = f"Pythonで{task}を実装するコードだけを生成してください。説明、コメント、コードブロック（```）は一切不要です。"
                    return model.generate_content(code_prompt).text.strip()
                raw_code_response = safe_api_call(generate_code_response)
                clean_code = clean_code_output(raw_code_response)
                formatted_response = format_response("Generated Code", clean_code, is_code=True)
                conversation_history.append({"role": "model", "parts": [formatted_response]})
                return formatted_response
                
            elif func_name == "review_code":
                formatted_response = process_code_tool("review", args, prompt, 
                    lambda code: model.generate_content(f"以下のPythonコードをレビューして、改善点や提案を自然言語で教えてください:\n{code}").text.strip())
                conversation_history.append({"role": "model", "parts": [formatted_response]})
                return formatted_response
                
            elif func_name == "run_code":
                code = args.get("code") or get_most_recent_code()
                if not code:
                    formatted_response = format_response("Error", "実行するコードが見つかりませんでした。")
                    conversation_history.append({"role": "model", "parts": [formatted_response]})
                    return formatted_response
                try:
                    with open("temp.py", "w") as f:
                        f.write(code)
                    result = subprocess.check_output(["python", "temp.py"], text=True, stderr=subprocess.STDOUT)
                    formatted_response = format_response("Execution", result.strip())
                except subprocess.CalledProcessError as e:
                    formatted_response = format_response("Execution Error", e.output.strip())
                finally:
                    if os.path.exists("temp.py"):
                        os.remove("temp.py")
                conversation_history.append({"role": "model", "parts": [formatted_response]})
                return formatted_response
                
            elif func_name == "debug_code":
                formatted_response = process_code_tool("debug", args, prompt, 
                    lambda code: model.generate_content(f"以下のPythonコードをデバッグして、潜在的なバグや問題点を自然言語で教えてください:\n{code}").text.strip())
                conversation_history.append({"role": "model", "parts": [formatted_response]})
                return formatted_response
                
            elif func_name == "save_code":
                code = args.get("code") or get_most_recent_code()
                if not code:
                    formatted_response = format_response("Error", "保存するコードが見つかりませんでした。")
                    conversation_history.append({"role": "model", "parts": [formatted_response]})
                    return formatted_response
                filename = args.get("filename", "output.py")
                with open(filename, "w") as f:
                    f.write(code)
                formatted_response = format_response("Saved", f"コードを {filename} に保存しました。")
                conversation_history.append({"role": "model", "parts": [formatted_response]})
                return formatted_response
                
            elif func_name == "edit_code":
                # ファイル名がない場合はプロンプトから抽出を試みる
                filename = args.get("filename")
                if not filename:
                    filename = extract_filename_from_prompt(prompt)
                
                if not filename:
                    formatted_response = format_response("Error", "編集するファイル名が指定されていません。")
                    conversation_history.append({"role": "model", "parts": [formatted_response]})
                    return formatted_response
                
                if not os.path.exists(filename):
                    formatted_response = format_response("Error", f"{filename} が見つかりませんでした。")
                elif not os.access(filename, os.R_OK):
                    formatted_response = format_response("Error", f"{filename} を読み取る権限がありません。")
                elif not os.access(filename, os.W_OK):
                    formatted_response = format_response("Error", f"{filename} を書き込む権限がありません。")
                else:
                    with open(filename, "r") as f:
                        code = f.read()
                    edit_instruction = args.get("instruction", prompt)
                    def generate_edit_response():
                        edit_prompt = f"以下のPythonコードを編集してください。指示: {edit_instruction}\nコード:\n{code}"
                        return model.generate_content(edit_prompt).text.strip()
                    edited_code = safe_api_call(generate_edit_response)
                    clean_code = clean_code_output(edited_code)
                    
                    # 変更前のコードと編集後のコードを比較
                    import difflib
                    diff = list(difflib.unified_diff(
                        code.splitlines(), 
                        clean_code.splitlines(),
                        fromfile=f"修正前: {filename}",
                        tofile=f"修正後: {filename}",
                        lineterm=''
                    ))
                    diff_text = '\n'.join(diff) if diff else "変更はありませんでした。"
                    
                    with open(filename, "w") as f:
                        f.write(clean_code)
                    
                    formatted_response = format_response("Edited", clean_code, is_code=True)
                    formatted_response += f"\n\nDiff:\n```diff\n{diff_text}\n```"
                
                conversation_history.append({"role": "model", "parts": [formatted_response]})
                return formatted_response
                
            elif func_name == "test_code":
                formatted_response = process_code_tool("test", args, prompt, 
                    lambda code: model.generate_content(f"以下のPythonコード用のテストコードを生成してください:\n{code}").text.strip(), 
                    is_code=True)
                conversation_history.append({"role": "model", "parts": [formatted_response]})
                return formatted_response
                
            elif func_name == "explain_code":
                formatted_response = process_code_tool("explain", args, prompt, 
                    lambda code: model.generate_content(f"以下のPythonコードの動作を自然言語で説明してください:\n{code}").text.strip())
                conversation_history.append({"role": "model", "parts": [formatted_response]})
                return formatted_response
                
            else:
                formatted_response = format_response("Error", f"不明な関数名 '{func_name}' です。")
                conversation_history.append({"role": "model", "parts": [formatted_response]})
                return formatted_response
    except json.JSONDecodeError:
        conversation_history.append({"role": "model", "parts": [assistant_response]})
        return assistant_response
    
    conversation_history.append({"role": "model", "parts": [assistant_response]})
    return assistant_response

def main():
    parser = argparse.ArgumentParser(description="CLI AI エージェント")
    parser.add_argument('--max_tokens', type=int, default=500, help="出力の最大トークン数")
    parser.add_argument('--context_length', type=int, default=10, help="保存する会話の最大数")
    parser.add_argument('--task', type=str, help="タスクを指定（例: コード生成）")
    parser.add_argument('--file', type=str, help="対象ファイル")
    args = parser.parse_args()

    global MAX_TOKENS, CONTEXT_LENGTH
    MAX_TOKENS = args.max_tokens
    CONTEXT_LENGTH = args.context_length

    if args.task == "コード生成" and args.file:
        prompt = f"Pythonで便利な関数を生成して{args.file}に保存してください。"
        response = chat_with_gemini(prompt)
        try:
            code_match = re.search(r"```python\n(.*?)\n```", response, re.DOTALL)
            if code_match:
                code = code_match.group(1).strip()
                with open(args.file, 'w') as f:
                    f.write(code)
                print(response)
                print(f"コードを {args.file} に保存しました。")
            else:
                raise IndexError("コードブロックが見つかりません")
        except IndexError as e:
            print(f"コードの抽出に失敗しました: {str(e)}")
            print(response)
        return

    print("CLI AI エージェントへようこそ。終了するには 'exit' または 'quit' と入力してください。")
    while True:
        try:
            user_input = input("User> ")
            if user_input.lower() in ["exit", "quit"]:
                print("エージェントを終了します。")
                break
            response = chat_with_gemini(user_input)
            print(response)
        except KeyboardInterrupt:
            print("\nエージェントを終了します。")
            break
        except Exception as e:
            print(f"エラーが発生しました: {str(e)}")
            print("もう一度試すか、別のコマンドを入力してください。")

if __name__ == '__main__':
    main()