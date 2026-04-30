import os

from langchain.tools import tool
# from ddgs import DDGS
from urllib.parse import urlparse

@tool("calculator", description="Performs arithmetic calculations. Use this for any math problems.")
def calculator(expression: str) -> str:
    print(f"=== CALCULATOR TOOL INVOKED === \n Expression: {expression}")
    return str(eval(expression))
