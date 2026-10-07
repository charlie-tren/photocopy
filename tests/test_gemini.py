"""The Gemini client rides out a demand spike and falls back to a second model.

Added 07/10/2026: twice in a week a 503 "high demand" failed the 18:00 frame,
because the client gave up inside six seconds and had nowhere else to go."""
import gemini


class _Resp:
    def __init__(self, code, text="", body=None):
        self.status_code, self.text, self._body = code, text, body

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise gemini.requests.HTTPError(f"{self.status_code}")


def _ok(text):
    return _Resp(200, body={"candidates": [{"content": {"parts": [{"text": text}]}}]})


SETTINGS = {"gemini": {"model": "primary", "fallback_model": "backup",
                       "endpoint": "https://x", "timeout_seconds": 1, "max_retries": 2}}


def _wire(monkeypatch, answers):
    calls, waits = [], []

    def post(url, **kw):
        model = url.rsplit("/", 1)[1].split(":")[0]
        calls.append(model)
        return answers[model].pop(0)
    monkeypatch.setattr(gemini.requests, "post", post)
    monkeypatch.setattr(gemini.time, "sleep", waits.append)
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    return calls, waits


def test_a_spike_on_the_first_model_is_answered_by_the_fallback(monkeypatch):
    busy = [_Resp(503, '{"error": {"status": "UNAVAILABLE"}}')] * 3
    calls, _ = _wire(monkeypatch, {"primary": list(busy), "backup": [_ok("a frame")]})
    assert gemini.generate("p", SETTINGS, 0.7) == "a frame"
    assert calls == ["primary"] * 3 + ["backup"]


def test_the_waits_are_long_enough_to_outlast_a_spike(monkeypatch):
    busy = [_Resp(503, "busy")] * 3
    _, waits = _wire(monkeypatch, {"primary": list(busy), "backup": [_ok("x")]})
    gemini.generate("p", SETTINGS, 0.7)
    assert sum(waits) >= 60, waits


def test_a_spike_that_clears_never_touches_the_fallback(monkeypatch):
    calls, _ = _wire(monkeypatch, {"primary": [_Resp(503, "busy"), _ok("ok")], "backup": []})
    assert gemini.generate("p", SETTINGS, 0.7) == "ok"
    assert "backup" not in calls


def test_a_bad_request_is_not_retried_on_another_model(monkeypatch):
    calls, _ = _wire(monkeypatch, {"primary": [_Resp(400, "bad")] * 3, "backup": [_ok("x")]})
    try:
        gemini.generate("p", SETTINGS, 0.7)
        raise AssertionError("a 400 should raise")
    except gemini.GeminiError:
        pass
    assert "backup" not in calls


def test_without_a_fallback_configured_it_still_raises(monkeypatch):
    calls, _ = _wire(monkeypatch, {"primary": [_Resp(503, "busy")] * 3})
    settings = {"gemini": {**SETTINGS["gemini"], "fallback_model": ""}}
    try:
        gemini.generate("p", settings, 0.7)
        raise AssertionError("should raise")
    except gemini.GeminiError as e:
        assert "503" in str(e)
