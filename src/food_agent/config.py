from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    amap_api_key: str = ""
    baidu_map_api_key: str = ""
    tavily_api_key: str = ""

    siliconflow_api_key: str = ""
    siliconflow_embedding_model: str = "BAAI/bge-m3"

    mysql_url: str = "mysql+pymysql://root:password@localhost:3306/food_agent?charset=utf8mb4"
    chroma_dir: str = "./chroma_data"

settings = Settings()
