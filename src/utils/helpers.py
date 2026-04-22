import yaml
import os

def load_config(config_path="config.yaml"):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    # This logic replaces ${VAR} with the actual secret from your system
    config['pinecone']['api_key'] = os.getenv('PINECONE_API_KEY')
    config['openai']['api_key'] = os.getenv('OPENAI_API_KEY')
    
    return confi 