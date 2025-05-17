"""Multi-agent project coordination module."""

from typing import List, Dict, Any

import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

class Agent:
    """Base class for AI agents."""

    def __init__(self, name: str, role_prompt: str, model: Any):
        self.name = name
        self.role_prompt = role_prompt
        self.model = model
        self.log: List[str] = []

    def send(self, message: str) -> str:
        """Send a message to the agent and get a response."""
        prompt = f"{self.role_prompt}\n{message}"
        logger.debug("%s prompt: %s", self.name, prompt)
        response = self.model.generate_content(prompt).text.strip()
        self.log.append(f"User: {message}")
        self.log.append(f"{self.name}: {response}")
        return response

    def get_log(self) -> str:
        """Return conversation log."""
        return "\n".join(self.log)


class ProjectCoordinator:
    """Coordinate conversations between multiple agents."""

    def __init__(self, model: Any):
        self.model = model
        # Instantiate agents with basic role descriptions
        self.front_agent = Agent(
            "FrontAI",
            "あなたはユーザーとの窓口となるAIです。指示を受け取り、SEAIとPGAIに伝達します。",
            model,
        )
        self.se_agent = Agent(
            "SEAI",
            "あなたはシステムエンジニアAIです。要件を整理し不明点をユーザーに確認します。",
            model,
        )
        self.pg_agent = Agent(
            "PGAI",
            "あなたはプログラミングAIです。与えられたタスクを実装し進捗を報告します。",
            model,
        )
        self.logs: Dict[str, List[str]] = {
            "front": [],
            "se": [],
            "pg": [],
        }

    def run(self) -> None:
        """Run interactive multi-agent session."""
        print("=== Multi Agent Project ===")
        goal = input("プロジェクトの目標を入力してください: ")
        self.logs["front"].append(f"Goal: {goal}")

        # Requirement gathering phase with SEAI
        print("--- 要件確認フェーズ ---")
        while True:
            question = self.se_agent.send(
                "追加でユーザーに確認すべき点があれば質問を1つだけ出力してください。なければ'完了'と答えてください。"
            )
            self.logs["se"].append(question)
            if "完了" in question:
                break
            answer = input(f"SEAI> {question}\nUser> ")
            self.se_agent.send(f"ユーザーの回答: {answer}")
            self.logs["se"].append(f"User: {answer}")

        summary = self.se_agent.send("要件を箇条書きでまとめてください。")
        print("=== 要件定義 ===")
        print(summary)
        self.logs["se"].append(summary)

        go = input("この要件でプロジェクトを開始しますか？ (y/n): ")
        if go.lower() != "y":
            print("プロジェクトを中止しました。")
            return

        print("--- 実装フェーズ ---")
        task_plan = self.se_agent.send("実装タスクをフェーズごとに洗い出してください。")
        print(task_plan)
        self.logs["se"].append(task_plan)

        self.pg_agent.send("以下のタスクを実行してください:\n" + task_plan)
        self.logs["pg"].append(task_plan)
        print("PGAIがタスクを実行中... (詳細はログを参照)")

    def export_logs(self) -> Dict[str, str]:
        """Return logs for user inspection."""
        return {
            "front": self.front_agent.get_log(),
            "se": self.se_agent.get_log(),
            "pg": self.pg_agent.get_log(),
        }
