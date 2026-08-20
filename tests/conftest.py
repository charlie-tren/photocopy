import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Nothing under test may write into the working copy. `step._log_rejection`
# resolves its path through `step.rel`, so a test that exercises the reject
# path without redirecting `rel` appends to the REAL data/rejections.jsonl -
# and the daily workflow runs pytest and then `git add -A`, so the fixture rows
# get committed. That is how 32 identical '{"prompt": "prompt"}' rows reached
# the production log: 8 CI runs x 4 rows, and not one real refusal among them.
#
# The log is the early-warning signal for the chain walking somewhere it
# shouldn't (docs/collapse.md), so filling it with fixtures does not just make
# a mess - it hides the thing it exists to show.
@pytest.fixture(autouse=True)
def _no_writes_into_the_repo(tmp_path, monkeypatch):
    import step
    monkeypatch.setattr(step, "rel", lambda p: str(tmp_path / p), raising=False)
