# tests/test_model_config.py
import collagent.graph as graph


def test_get_model_honors_env(monkeypatch):
    # Switching providers must be a config change only: get_model reads these
    # three env vars at call time and builds an OpenAI-compatible client.
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_NAME", "llama-3.3-70b-versatile")
    m = graph.get_model()
    assert m.model_name == "llama-3.3-70b-versatile"
    assert str(m.openai_api_base) == "https://api.groq.com/openai/v1"
