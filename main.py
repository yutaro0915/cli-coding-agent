from openai import OpenAI

# APIキーを設定
client = OpenAI(api_key="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")

# GPTモデルと会話する関数
def chat_with_gpt(prompt, model="gpt-4o-mini"):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "あなたは役立つアシスタントです。"},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

# 使用例
user_input = "flaskについておしえて！"
response = chat_with_gpt(user_input)
print(response)