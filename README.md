# CLI Coding Agent

コマンドラインで動作するAIアシスタントです。Google Generative AI (Gemini) を利用して対話型のチャット体験を提供します。
## セットアップ

1. 必要なパッケージをインストール:
```bash
pip install google-generativeai
```
このパッケージは `requirements.txt` にも含まれています。

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

### オプション
- `--max_tokens`: 出力の最大トークン数（デフォルト: 150）
- `--context_length`: 保持する会話の最大数（デフォルト: 10）

- `--model`: 使用するモデル名 (例: gemini-2.0-flash, gemini-2.0-pro)

## 終了方法
会話を終了するには `exit` または `quit` と入力してください。
