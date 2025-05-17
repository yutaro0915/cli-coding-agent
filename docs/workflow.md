# ワークフロー機能ガイド

CLIコーディングアシスタントのワークフロー機能は、複数のステップを組み合わせて複雑なタスクを実行するための機能です。
インタラクティブなコード編集と事前定義された連続タスクの両方の利点を活かすことができます。

## ワークフローの概念

ワークフローは以下の要素で構成されています：

1. **ステップ**: 個々の処理単位。コード生成、編集、ファイル操作など
2. **フロー制御**: ステップの実行順序や条件分岐を定義
3. **インタラクティブモード**: 各ステップの結果をユーザーが確認・編集可能

## 利用可能なステップタイプ

- `code_generation`: コードを生成
- `code_editing`: 既存コードを編集
- `code_review`: コードをレビュー
- `code_refactoring`: コードをリファクタリング
- `test_generation`: テストコードを生成
- `documentation`: ドキュメントを生成
- `user_input`: ユーザーからの入力を受け付ける
- `file_operation`: ファイルの読み書き
- `conditional`: 条件分岐
- `loop`: 繰り返し処理

## ワークフローの作成方法

### 1. 目標指定によるAI自動作成

```
Webサーバーを構築したい
```

このような高レベルの目標を指定するだけで、AIが自動的に最適なワークフローを構築します。AIは目標を分析し、必要なステップを特定して、最適な順序で配置したワークフローを生成します。

### 2. JSONファイルからの読み込み

事前に定義されたワークフローはJSONファイルとして保存・編集できます：

```json
{
  "name": "Webサーバー作成",
  "description": "FlaskでRESTful APIを作成",
  "start_step": "generate_server",
  "steps": {
    "generate_server": {
      "step_type": "code_generation",
      "description": "APIサーバーのコードを生成",
      "arguments": {
        "task": "Flaskで簡単なRESTful APIを実装する"
      },
      "next_on_success": "save_code"
    },
    "save_code": {
      "step_type": "file_operation",
      "description": "生成したコードを保存",
      "arguments": {
        "operation": "write",
        "filename": "app.py",
        "previous_step": "generate_server"
      },
      "next_on_success": "generate_test"
    },
    "generate_test": {
      "step_type": "test_generation",
      "description": "テストコードを生成",
      "arguments": {
        "filename": "app.py"
      },
      "next_on_success": "save_test"
    },
    "save_test": {
      "step_type": "file_operation",
      "description": "テストコードを保存",
      "arguments": {
        "operation": "write",
        "filename": "test_app.py",
        "previous_step": "generate_test"
      }
    }
  }
}
```

## ワークフローの実行

### コマンドラインからの実行

```bash
python main.py --workflow my_workflow.json
```

インタラクティブモードをオフにする場合：

```bash
python main.py --workflow my_workflow.json --non-interactive
```

### インタラクティブセッションでの実行

対話モードで以下のように実行できます：

```
User> ワークフロー my_workflow.json を実行して
```

または目標を直接指定して自動実行：

```
User> Todoアプリを作成するワークフローを実行して
```

## インタラクティブモードの操作

ワークフローの各ステップ実行後、以下の選択肢があります：

- `y`: 結果を承認し次のステップへ進む
- `n`: 結果を却下しワークフローを終了
- `e`: 結果を編集してから次へ進む

## ワークフローの例

### シンプルなウェブアプリケーション作成

```json
{
  "name": "ウェブアプリケーション作成",
  "description": "HTMLとJavaScriptを使用した簡単なウェブアプリケーションの作成",
  "start_step": "create_html",
  "steps": {
    "create_html": {
      "step_type": "code_generation",
      "description": "HTMLファイルを生成",
      "arguments": {
        "task": "シンプルなTodoリストのHTMLページを作成"
      },
      "next_on_success": "save_html"
    },
    "save_html": {
      "step_type": "file_operation",
      "description": "HTMLを保存",
      "arguments": {
        "operation": "write",
        "filename": "index.html",
        "previous_step": "create_html"
      },
      "next_on_success": "create_js"
    },
    "create_js": {
      "step_type": "code_generation",
      "description": "JavaScriptファイルを生成",
      "arguments": {
        "task": "Todoリスト用のJavaScript機能を実装する"
      },
      "next_on_success": "save_js"
    },
    "save_js": {
      "step_type": "file_operation",
      "description": "JavaScriptを保存",
      "arguments": {
        "operation": "write",
        "filename": "app.js",
        "previous_step": "create_js"
      }
    }
  }
}
```

## ベストプラクティス

1. **ステップの粒度**: 一つのステップは一つの明確な作業に対応させる
2. **エラーハンドリング**: 重要なステップには必ず`next_on_failure`を設定する
3. **ワークフローの再利用**: 共通パターンはワークフローとして保存し再利用する
4. **条件分岐の活用**: 動的な処理フローには条件分岐を使う
5. **AI制御の活用**: 複雑なプロジェクトではAI制御ワークフローを使用し、タスクの自動生成と進行管理を任せる

## 条件式の安全な評価

`conditional` ステップでは `{step_id.result_key}` 形式で他のステップ結果を参照する条件式を記述できます。式の評価には Python の `eval()` を使用せず、論理・比較演算子のみを解釈する簡易パーサーで処理します。これにより、関数実行や属性アクセスなど任意のコードが実行されるリスクを避けています。
