import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def get_config():
    """
    Returns a dictionary of configuration settings.
    """
    config = {
        "langchain_api_key": os.getenv("LANGCHAIN_API_KEY"),
        "langchain_tracing_v2": os.getenv("LANGCHAIN_TRACING_V2", "true"),
        "langchain_project": os.getenv("LANGCHAIN_PROJECT", "lab22"),
        "openai_api_base": os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "model_name": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
    }
    return config

def setup_langsmith():
    """
    Sets the environment variables for LangSmith tracing.
    """
    config = get_config()
    os.environ["LANGCHAIN_TRACING_V2"] = config["langchain_tracing_v2"]
    os.environ["LANGCHAIN_API_KEY"] = config["langchain_api_key"]
    os.environ["LANGCHAIN_PROJECT"] = config["langchain_project"]
    # Ensure project exists or is set correctly

if __name__ == "__main__":
    conf = get_config()
    print("[SUCCESS] Config loaded successfully")
    print(f"   LangSmith project : {conf['langchain_project']}")
    print(f"   OpenAI endpoint   : {conf['openai_api_base']}")
    print(f"   Default LLM model : {conf['model_name']}")
    print(f"   Embedding model   : {conf['embedding_model']}")
