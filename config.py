"""全局配置：从环境变量 / .env 读取，集中管理所有可调参数。"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 加载项目根目录的 .env（若存在）
load_dotenv(Path(__file__).parent / ".env")


class Settings:
    # 大模型接入（OpenAI 兼容协议）
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    llm_model: str = os.getenv("LLM_MODEL", "deepseek-chat")
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    max_tool_rounds: int = int(os.getenv("MAX_TOOL_ROUNDS", "6"))

    @property
    def llm_ready(self) -> bool:
        """是否已配置可用的 API Key。"""
        return bool(self.llm_api_key)


settings = Settings()
