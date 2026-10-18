from types import SimpleNamespace

import anthropic
import pytest

import claude
import describe
import gemini
import safety


def _msg(text='{"safe": true, "reason": "ok"}', stop="end_turn"):
    return SimpleNamespace(
        stop_reason=stop,
        content=[SimpleNamespace(type="thinking", thinking=""),
                 SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=1000, output_tokens=2000))


def _api_error(cls, message):
    """An SDK error without a live response, whatever HTTP library it uses."""
    exc = cls.__new__(cls)
    Exception.__init__(exc, message)
    exc.message = message
    return exc


class Fake:
    def __init__(self):
        self.calls, self.reply, self.raises = [], _msg(), None
        self.messages = SimpleNamespace(create=self._create("plain"))
        self.beta = SimpleNamespace(
            messages=SimpleNamespace(create=self._create("beta")))

    def _create(self, path):
        def create(**kw):
            self.calls.append((path, kw))
            if self.raises:
                raise self.raises
            return self.reply
        return create


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(claude, "_off", None)
    fake = Fake()
    monkeypatch.setattr(claude, "_client", fake)
    return fake


def _gemini_answers(monkeypatch, text):
    asked = []
    monkeypatch.setattr(gemini, "_post", lambda payload, settings:
                        asked.append(payload) or text)
    return asked


def test_safety_check_runs_on_haiku_with_the_image_first(live, monkeypatch):
    asked = _gemini_answers(monkeypatch, '{"safe": false, "reason": "gemini"}')
    safe, reason = safety.check_image(b"img", {"gemini": {}, "safety": {}},
                                      mime="image/png")
    assert safe is True and asked == []
    path, kw = live.calls[0]
    assert path == "plain" and kw["model"] == "claude-haiku-5-5"
    blocks = kw["messages"][0]["content"]
    assert [b["type"] for b in blocks] == ["image", "text"]
    assert blocks[0]["source"]["media_type"] == "image/png"


def test_describer_runs_on_sonnet(live, monkeypatch):
    _gemini_answers(monkeypatch, "{}")
    try:
        describe.describe(b"img", {"gemini": {"temperature": 0.7}})
    except Exception:                                 # noqa: BLE001
        pass   # the stub reply is not a description; the model is what is checked
    path, kw = live.calls[0]
    assert path == "beta" and kw["model"] == "claude-sonnet-5-5"
    assert kw["fallbacks"] == "default" and "temperature" not in kw


def test_missing_key_falls_back_to_gemini_with_a_warning(live, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    asked = _gemini_answers(monkeypatch, '{"safe": true, "reason": "gemini"}')
    safe, reason = safety.check_image(b"img", {"gemini": {}, "safety": {}})
    assert reason == "gemini" and len(asked) == 1 and live.calls == []
    assert "::warning::" in capsys.readouterr().out


def test_safety_still_fails_closed_when_both_providers_die(live, monkeypatch):
    live.raises = _api_error(anthropic.InternalServerError, "overloaded")

    def dead(payload, settings):
        raise gemini.GeminiError("HTTP 503")
    monkeypatch.setattr(gemini, "_post", dead)
    safe, reason = safety.check_image(b"img", {"gemini": {}, "safety": {}})
    assert safe is False and "503" in reason


def test_refusal_falls_back_for_that_call_only(live, monkeypatch):
    live.reply = _msg(stop="refusal")
    _gemini_answers(monkeypatch, '{"safe": false, "reason": "gemini"}')
    assert safety.check_image(b"img", {"gemini": {}, "safety": {}}) == \
        (False, "gemini")
    assert claude._off is None


def test_usage_and_cost_are_logged(live, monkeypatch, capsys):
    _gemini_answers(monkeypatch, "{}")
    safety.check_image(b"img", {"gemini": {}, "safety": {}})
    assert "claude-haiku-5-5 [judge] in=1000 out=2000 US$0.0011" in \
        capsys.readouterr().out
