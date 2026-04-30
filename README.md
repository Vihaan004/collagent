# Collagent

**Current version:** A simple agent with access to your Canvas LMS Account:) Built with LangGraph. CLI interface.

**Goal:** An agentic interface between a student and their university. Enriched with indexed data and web search for contextual assitance. Dedicated pipelines for networking, clubs, organizations, sports, events, and more.

## Setup
Create a virtual environment and install deps:
```sh
uv venv
uv pip install -e .
```
Set your keys. 
```sh
export OPENAI_API_KEY="..." # ASU provides free llm access
export CANVAS_API_TOKEN="..." # canvas > account > settings
```
Run the CLI:
```sh
collagent run
```