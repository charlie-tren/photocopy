# Why this project is built around collapse

The mechanism is a telephone game: draw a picture, describe the picture, draw the
description, describe that. It is not a new idea. Robert Hodgin ran it between
Midjourney and GPT-4, Kawandeep Virdee has written about visual wandering with
image-generation feedback loops, and there is a 2025 paper, *The Telephone Game:
Evaluating Semantic Drift in Unified Models*. What is new here is only that
nobody runs it daily, in public, without a hand on it.

## The finding that shapes the design

These loops **converge**. They do not wander. In one study of 700 runs the chains
collapsed into roughly twelve stock scenes - gothic cathedrals, pastoral
landscapes, rainy Parisian streets - regardless of how specific or strange the
starting prompt was. Left alone, this project would be visually finished within
a couple of months, and the back half of its archive would be three hundred
near-identical pictures of a cathedral.

So "the drift is the point" is exactly the claim the evidence disagrees with, and
building as though it were true would have produced a dead site with a good
description of itself.

## What pushes back, and why none of it is a nudge

The constraint that mattered was that nothing enters the chain from outside. A
daily injected random noun would keep the pictures moving, but the movement would
be mine, not the loop's, and the piece would stop being evidence of anything.
Both mechanisms below take the run's own past as their only input.

**1. A schema instead of prose** (`describe.py`). Convergence starts in the
language. A vision model left to write freely slides toward evocative generic
prose, that prose draws a generic image, and the generic image is described more
generically still. Six fixed slots make that slide inexpressible. The `anomaly`
slot is the load-bearing one: it forces the single most specific thing in the
frame to survive into the next prompt, where free prose would have smoothed it
into atmosphere.

**2. A ban list the run writes for itself** (`avoid.py`). Any content word
present in at least four of the last six descriptions is forbidden in the next
one. Presence, not frequency: a word used nine times in one description is a tic
inside that frame, whereas a word appearing in four frames out of six is the run
circling. This is The Aftertimes' `trends.py`/`avoid.py` pair, transplanted.

## The backstop, which is also the scoreboard

Neither mechanism prevents collapse. They buy frames. So the third piece is a
detector (`collapse.py`), and the number it produces - how many frames a run
survived - is the thing the site actually reports.

Both signals must agree before a run is sealed, because either alone lies:

- *Text only.* A run can hold one subject while genuinely restyling it daily. The
  words repeat and the pictures do not. Sealing there kills a live run.
- *Image only.* Two frames can be near-identical while the description is visibly
  casting around for an exit. That run is still trying, and often escapes.

So: mean pairwise cosine over description word-sets is at or above `0.72`, **and**
mean pairwise dHash distance across the last five images is at or below `8` of a
possible 64, for three consecutive frames, and never before frame 12.

When a run is sealed it is fixed forever and a new one opens from the next
written seed. Seeds cycle rather than being consumed, because two runs from the
same start are the only way to tell whether the rules above are doing anything or
the chain was always going where it went.
