import os
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from src.utils.report_worker import get_report_llm

llm = get_report_llm()
response = llm.invoke("Hello, return exactly the word 'Hi'")
print("Type of response.content:", type(response.content))
print("Value of response.content:", response.content)
