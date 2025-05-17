# CLI Coding Agent

コマンドラインで動作するAIアシスタントです。Google Generative AI (Gemini) を利用して対話型のチャット体験を提供します。
## セットアップ

1. リポジトリをクローンし、依存パッケージをインストールします。
```bash
git clone <repository-url>
cd cli-coding-agent
pip install -r requirements.txt
```
Gemini API クライアント(`google-generativeai`)などの必要なライブラリが全てインストールされます。

2. Google APIキーを環境変数として設定:
```bash
export GOOGLE_API_KEY='your-key'
```

## 使い方

基本的な実行:
```bash
python main.py
```

オプション付きの実行:
```bash
python main.py --max_tokens 200 --context_length 15 --model gemini-2.0-flash
```

ワークフローを指定して実行する例:
```bash
python main.py --workflow my_workflow.json
```
`--non-interactive` を付けるとユーザー確認なしで全ステップが順次実行されます。

### タスク指定例

特定のツールを直接実行できます。

```bash
python main.py --task generate_code --file output.py
```

利用可能なタスクは `generate_code`、`review_code`、`debug_code`、`test_code` などです。
各タスクでは `--file` オプションで入力ファイルや出力先を指定します。

```bash
python main.py --task review_code --file foo.py
```

### マルチエージェントモード

複数のAIエージェントが協力してタスクを進めるモードを起動するには以下のオプションを使用します。

```bash
python main.py --multi-agent
```

セッション終了後、`front_log.txt`、`se_log.txt`、`pg_log.txt` として会話ログが保存されます。

### オプション
- `--max_tokens`: 出力の最大トークン数（デフォルト: 500）
- `--context_length`: 保持する会話の最大数（デフォルト: 10）

- `--model`: 使用するモデル名 (例: gemini-2.0-flash, gemini-2.0-pro)
- `--workflow`: JSONで定義したワークフローを実行
- `--non-interactive`: ワークフロー実行時に確認を求めない
- `--multi-agent`: マルチエージェントプロジェクトモードを起動

## 終了方法
会話を終了するには `exit` または `quit` と入力してください。

### フロントエンドUI
Streamlit を利用した簡易フロントエンドを `frontend` ディレクトリに追加しています。
次のコマンドで起動し、ブラウザからエージェントとの対話を試すことができます。
```bash
streamlit run frontend/app.py
```
サイドバーでプロジェクトを選択し、中央下部の入力欄から FrontAI とのチャットを行えます。右側のログ欄には SEAI と PGAI の会話履歴が表示されます。
