from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_hostname: str 
    database_port: str
    database_password: str
    database_name: str
    database_username: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    pinecone_api_key: str
    pinecone_dense_index_host: str
    index_name: str
    namespace_name: str

    class Config:
        env_file = ".env"
        
#note for me, dont forget to instantiate the Settings class to use it  
settings = Settings()