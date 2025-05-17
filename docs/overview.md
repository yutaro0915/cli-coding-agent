# CLIコーディングアシスタントの概要

## 構造概要

このプロジェクトは、Google Gemini APIを利用したCLIベースのコーディングアシスタントです。AIを活用して、コード生成、レビュー、編集などの操作をコマンドラインから実行できます。

### ファイル構成

プロジェクトは主に2つのファイルで構成されています：

1. **main.py** - メインアプリケーションとCLIインターフェース
2. **tools.py** - 各種ツール機能のモジュール

## 主要コンポーネント

### 1. CLIAssistant クラス (main.py)

- **役割**: ユーザーとの対話、会話履歴の管理、ツールの呼び出し
- **主な機能**:
  - `chat_with_gemini()`: Gemini APIとの対話処理
  - `safe_api_call()`: APIリクエストのリトライ処理
  - `get_most_recent_code()`: 会話履歴から最新のコードを取得
  - `run_cli()`: CLIループの実行
  - `cleanup()`: 一時ファイルの削除

### 2. ツール関数 (tools.py)

- **役割**: 各種コード操作のロジック実装
- **主な関数**:
  - `handle_generate_code()`: コード生成
  - `handle_edit_code()`: 既存コードの編集
  - `handle_save_code()`: コードをファイルに保存
  - `process_code_tool()`: 汎用的なコード処理パターン
  - `clean_code_output()`: マークダウンなどからコードを抽出
  - `format_response()`: 統一された応答フォーマットを生成

### 3. サポート関数

- `extract_filename_from_prompt()`: プロンプトからファイル名を抽出
- その他、フォーマット、正規表現処理などのユーティリティ関数

## 利用可能なツール

1. `generate_code`: Pythonコードを生成
2. `review_code`: コードをレビューし改善点を提案
3. `debug_code`: コードの潜在的なバグを指摘
4. `save_code`: 生成したコードをファイルに保存
5. `edit_code`: 既存コードを読み込んで編集
6. `test_code`: コード用のテストを生成
7. `explain_code`: コードの動作を説明
8. `refactor_code`: コードをリファクタリング
9. `generate_docs`: コードのドキュメントを生成

※ 以前は実行機能 (`run_code`) もありましたが、現在は削除されIDEの実行機能を使用するように設計されています。

## 使用方法

1. 環境変数 `GOOGLE_API_KEY` にGoogle APIキーを設定
2. 以下のようにCLIから実行:
   ```bash
   python main.py
   ```
3. オプションとして以下を指定可能:
   ```bash
   python main.py --max_tokens 800 --context_length 15 --model "gemini-2.0-pro" --log_level DEBUG
   ```
4. 特定のタスク用のコマンド:
   ```bash
   python main.py --task generate_code --file output.py
   ```

別の例:

```bash
python main.py --task review_code --file foo.py
```

## 拡張・開発のための注意点

- 新しいツールを追加する場合は `tools.py` に関数を実装し、`main.py` の `chat_with_gemini()` メソッドでの条件分岐に追加します
- コード実行など環境に依存する機能は削除されています
- 関数は再利用性を高めるため、独立したパラメータ構造になっています
