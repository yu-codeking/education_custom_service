from pathlib import Path

from pydantic_settings import SettingsConfigDict, BaseSettings

PROJECT_DIR = Path(__file__).resolve().parents[2]

ENV_FILE_PATH = PROJECT_DIR / ".env"


class Settings(BaseSettings):
    llm_model: str
    llm_base_url: str
    llm_api_key: str
    edu_api_base_url: str  # 教育业务数据中台地址（edu-data 的 FastAPI 服务）
    database_url: str  # 对话状态库（customer_service.dialogue_states）
    app_host: str
    app_port: int

    model_config = SettingsConfigDict(env_file=ENV_FILE_PATH, env_file_encoding="utf-8")


settings = Settings()  # type:ignore
