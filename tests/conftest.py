import os
import tempfile

# Override connection parameters so python-dotenv doesn't overwrite them
os.environ["DB_HOST"] = ""
os.environ["DB_PORT"] = ""
os.environ["DB_USERNAME"] = ""
os.environ["DB_PASSWORD"] = ""
os.environ["DB_DATABASE"] = ""

temp_db_path = os.path.join(tempfile.gettempdir(), "finheal_test_temp.db")
os.environ["DATABASE_URL"] = f"sqlite:///{temp_db_path}"
