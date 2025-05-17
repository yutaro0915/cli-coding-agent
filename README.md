# CLI Coding Agent

コマンドラインで動作するAIアシスタントです。OpenAI APIを使用して対話型のチャット体験を提供します。

## セットアップ

1. 必要なパッケージをインストール:
```bash
pip install openai
```

2. OpenAI APIキーを環境変数として設定:
```bash
export OPENAI_API_KEY='your-api-key-here'
```

## 使い方

基本的な実行:
```bash
python main.py
```

オプション付きの実行:
```bash
python main.py --max_tokens 200 --context_length 15
```

### マルチエージェントモード

複数のAIエージェントが協力してタスクを進めるモードを起動するには以下のオプションを使用します。

```bash
python main.py --multi-agent
```

セッション終了後、`front_log.txt`、`se_log.txt`、`pg_log.txt` として会話ログが保存されます。

### オプション
- `--max_tokens`: 出力の最大トークン数（デフォルト: 150）
- `--context_length`: 保持する会話の最大数（デフォルト: 10）

## 終了方法
会話を終了するには `exit` または `quit` と入力してください。
