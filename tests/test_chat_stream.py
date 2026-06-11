import json

from collagent.api.routes.chat import sse_format


def test_sse_format():
    line = sse_format({"type": "token", "content": "hi"})
    assert line == 'data: {"type": "token", "content": "hi"}\n\n'
    assert json.loads(line[len("data: "):].strip()) == {"type": "token", "content": "hi"}
