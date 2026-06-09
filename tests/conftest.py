import os

# Override connection parameters so python-dotenv doesn't overwrite them
os.environ["DB_HOST"] = ""
os.environ["DB_PORT"] = ""
os.environ["DB_USERNAME"] = ""
os.environ["DB_PASSWORD"] = ""
os.environ["DB_DATABASE"] = ""
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
