import os
from pathlib import Path
import streamlit as st
import google.generativeai as genai

from agent_team import Agent

MODEL_NAME = "gemini-2.0-flash"

# Google APIキーの確認
API_KEY = os.environ.get("GOOGLE_API_KEY")
if not API_KEY:
    st.error("GOOGLE_API_KEYが設定されていません。環境変数を設定してください。")
    st.stop()

# モデル設定
genai.configure(api_key=API_KEY)


def init_agents():
    """フロントAI、SEAI、PGAIを初期化"""
    model = genai.GenerativeModel(MODEL_NAME)
    front = Agent(
        "FrontAI",
        "あなたはユーザーとの窓口となるAIです。指示を受け取り、SEAIとPGAIに伝達します。",
        model,
    )
    se = Agent(
        "SEAI",
        "あなたはシステムエンジニアAIです。要件を整理し不明点をユーザーに確認します。",
        model,
    )
    pg = Agent(
        "PGAI",
        "あなたはプログラミングAIです。与えられたタスクを実装し進捗を報告します。",
        model,
    )
    return front, se, pg


# セッションステートの初期化
if "agents" not in st.session_state:
    st.session_state.front, st.session_state.se, st.session_state.pg = init_agents()
    st.session_state.chat_log = []
    st.session_state.se_log = []
    st.session_state.pg_log = []

st.set_page_config(layout="wide")

# プロジェクト選択サイドバー
project_root = Path("projects")
projects = [p.name for p in project_root.iterdir() if p.is_dir()] if project_root.exists() else []
selected_project = st.sidebar.selectbox("プロジェクト", ["default"] + projects)

# 2列レイアウト: メインチャット / エージェントログ
main_col, log_col = st.columns([3, 1])

with main_col:
    st.header("FrontAI Chat")
    for role, msg in st.session_state.chat_log:
        st.markdown(f"**{role}**: {msg}")

    user_msg = st.chat_input("メッセージを入力")
    if user_msg:
        st.session_state.chat_log.append(("User", user_msg))
        front_reply = st.session_state.front.send(user_msg)
        st.session_state.chat_log.append(("FrontAI", front_reply))

        se_reply = st.session_state.se.send(front_reply)
        pg_reply = st.session_state.pg.send(se_reply)

        st.session_state.se_log.append(f"FrontAI -> SEAI: {front_reply}")
        st.session_state.se_log.append(f"SEAI: {se_reply}")
        st.session_state.pg_log.append(f"SEAI -> PGAI: {se_reply}")
        st.session_state.pg_log.append(f"PGAI: {pg_reply}")

        st.experimental_rerun()

with log_col:
    st.subheader("Agent Logs")
    st.markdown("### SEAI")
    for log in st.session_state.se_log:
        st.text(log)

    st.markdown("### PGAI")
    for log in st.session_state.pg_log:
        st.text(log)
