# Convergence, and why the chain is never reset

The mechanism is a telephone game: draw a picture, describe the picture, draw the
description, describe that. It is not a new idea. Robert Hodgin ran it between
Midjourney and GPT-4, Kawandeep Virdee has written about visual wandering with
image-generation feedback loops, and there is a 2025 paper, *The Telephone Game:
Evaluating Semantic Drift in Unified Models*. What is new here is only that
nobody runs it daily, in public, without a hand on it.

## The finding

These loops **converge**. They do not wander. In one study of 700 runs the chains
collapsed into roughly twelve stock scenes - gothic cathedrals, pastoral
landscapes, rainy Parisian streets - regardless of how specific or strange the
starting prompt was.

So "the drift is the point" is exactly the claim the evidence disagrees with, and
this project should be read as a test of it rather than an illustration of it.

## What pushes back, and why none of it is a nudge

The constraint that mattered was that nothing enters the chain from outside. A
daily injected random noun would keep the pictures moving, but the movement would
be Charlie's, not the loop's, and the piece would stop being evidence of
anything. Both mechanisms below take the chain's own past as their only input.

**1. A schema instead of prose** (`describe.py`). Convergence starts in the
language. A vision model left to write freely slides toward evocative generic
prose, that prose draws a generic image, and the generic image is described more
generically still. Six fixed slots make that slide inexpressible. The `anomaly`
slot is the load-bearing one: it forces the single most specific thing in the
frame to survive into the next prompt, where free prose would have smoothed it
into atmosphere.

**2. A ban list the chain writes for itself** (`avoid.py`). Any content word
present in at least four of the last six descriptions is forbidden in the next
one. Presence, not frequency: a word used nine times in one description is a tic
inside that frame, whereas a word appearing in four frames out of six is the
chain circling. This is The Aftertimes' `trends.py`/`avoid.py` pair, transplanted.

## There is no third mechanism

An earlier draft had a collapse detector that sealed a chain once it stopped
moving and started a fresh one from a new seed. **That was cut deliberately.**
There are no runs, no seals, no restarts. One chain, started once, going wherever
it goes.

This is a real bet against the literature, and it should be held to honestly: if
the chain locks into one image at frame 40, the site will show that image every
day after frame 40, and that will be the result. Do not quietly add a reset later
to make the page look livelier. If the mechanisms above are not enough, the
interesting fact is that they were not enough.

## Where this does not apply

Everything above is an argument about **aesthetics**: movement that came from
Charlie is not evidence of anything, so the chain is not nudged toward or away
from any subject. That argument has a boundary, and `safety.py` is on the other
side of it.

Frames 3-7 walked from a folded-brass figure to a nude male body seen from
behind, and by frame 7 to a crouched figure whose buttocks filled the frame. The
site came down on 17/08/2026 and those frames were removed.

The instructive part: **no description was ever lewd.** The words stayed flat and
clinical - "a polished gold male mannequin", "standing upright facing the back
wall" - and a word filter would have caught nothing. The nudity came from the
image model reading an unclothed mannequin in a tiled wet room, and then from the
describer accurately recording what had been drawn, which drew it harder. The
loop was working exactly as designed. That is the point: **an unsupervised loop
publishing daily under someone's own name needs a floor that is not itself part
of the loop.**

So the guard is an outside constraint, deliberately, and it is not pretending
otherwise:

- the describer is told not to record anatomy, and stripped if it does
- the drawn prompt clothes the figure
- **every frame is looked at by a vision classifier before it is kept**, and a
  frame that fails is redrawn up to three times, after which the day is
  abandoned with no frame at all

Only the third layer knows what was actually drawn; the first two are wording
that either model is free to ignore. Do not remove the classifier and keep the
wording - that is a guard in appearance only. A missing frame is a visible,
explicable gap. A bad frame is on the internet under Charlie's name.

This costs the project something real and it should be said plainly: the chain
can no longer go everywhere it might have gone, and "unsupervised" is now
"unsupervised within a floor". That is a smaller claim than the one the project
started with, and it is the honest one.

## The second failure: erosion, not drift (28/08/2026)

The nudity in frames 3-7 was drift - the chain walking somewhere. What happened
between frames 2 and 12 of the diver chain was different and worth naming
separately, because the fix is different.

The clothes came off one thread at a time, and the `covering` slot recorded every
step of it:

    2-4   jumpsuit
    5-9   top, shirt, turtleneck
    10    a tan turtleneck sweater
    11    an orange short-sleeved shirt
    12    an orange sleeveless top

Nothing anatomical was ever drawn. No frame was refused. Every step was a
faithful description of the frame before it. **Clothing is incidental detail -
it is never the subject and never the anomaly - and a lossy describer drops a
little incidental detail every frame.** The figure is the stable core; the
clothes are the thing that erodes off it.

That is a general property of this loop, not a fact about clothes. Anything the
schema does not actively hold in place will thin out over enough frames, and the
`anomaly` slot only protects ONE detail per frame. The 22/08 `covering` slot was
the right instinct and was not enough on its own: giving a detail a slot makes
its erosion legible, it does not stop it.

What stops it is re-assertion from outside the loop. The clothing floor is
stated by the DRAWER on every single frame, independently of what the describer
noticed, because anything that depends on the description inherits the
description's decay.

**And the ban list was making it worse.** `avoid.py` forbids any content word
present in four of the last six descriptions - so a figure that stays dressed
the same way for a week gets its own clothes banned. The live block on 28/08
read: *belt, dark, field, grey, harvested, **mannequin**, plastic, raised, soft,
**trousers**, woven*. The describer was being told, in writing, that it may not
say trousers; and with "mannequin" gone too it reaches for "figure", "dummy",
"body" - the exact anatomy vocabulary the other floor exists to undo.

So the two anti-collapse mechanisms were quietly fighting the two safety floors,
and the floors were losing one word at a time. `safety.PROTECTED` is now excluded
from the counter. It is deliberately short: every exemption is a small hole in
the thing that stops the chain circling, and these are only cheap because
clothing is not what the project is measuring.

## What is still measured

`collapse.py` reports and never acts. Two numbers are recorded on every frame and
shown on the page:

- how alike the last five DESCRIPTIONS are (cosine over content-word sets)
- how far apart the last five IMAGES are (mean pairwise dHash distance, 0-64)

Both, because either alone lies. The words can repeat while the pictures
genuinely change, and two frames can look identical while the description is
visibly casting around for a way out. They exist so it is possible to say whether
the schema and the ban list did anything, which is the only question this project
can actually answer.
