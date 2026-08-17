# Photocopy

A machine is shown yesterday's photograph and nothing else. It fills in six
slots describing what it can see. Those six lines are the entire prompt for
today's photograph. Then it is shown that one.

No memory, no earlier picture, no earlier words, no idea what it is looking at.
One frame a day, forever. One chain, started once, never reset.

**OFFLINE as at 17/08/2026.** Pages is disabled on this repo while the decency
guard is verified - see "The floor" below. Re-enabling Pages on `main` puts it
back at <https://charlietrenorden.com/photocopy/>.

It is not a self-portrait. Nothing in the loop tells the model that the figure
is it, and nothing asks it to draw itself - it is shown a picture, it writes
down what it can see, and that description draws the next picture.

## The loop

| Stage | File | What happens |
|---|---|---|
| Describe | `describe.py` | Gemini vision looks at frame N and fills six slots |
| Avoid | `avoid.py` | Words the run has leaned on lately are banned from that description |
| Draw | `draw.py` | The six slots become the prompt; Cloudflare Workers AI draws frame N+1 |
| Check | `safety.py` | The drawn frame is looked at; anything indecent is redrawn or the day is dropped |
| Measure | `collapse.py` | How far have the words and the pictures moved lately? Reported, never acted on |
| Render | `render.py` | Rebuild the viewer |

`step.py` is the daily entry point and owns all the IO. Everything else is pure
functions over plain dicts.

These loops are known to converge rather than wander, and this one is a bet that
a schema and a self-generated ban list can hold it off without anything entering
from outside. **Read [docs/collapse.md](docs/collapse.md) before changing
anything in `describe.py` or `avoid.py`** - and in particular before adding any
kind of automatic reset, which was considered and cut on purpose.

## The floor

Frames 3-7 drifted into nudity and were removed on 17/08/2026; the chain is back
to frame 1. `safety.py` is a deliberate outside constraint on what may be
published - the only one in the project - and `docs/collapse.md` explains why it
is an exception to "nothing enters the chain from outside". Before the site goes
back up, run the `check-guard` workflow: it puts the classifier in front of the
five real frames that caused this and fails if it disagrees with the human call.

## Running it

```bash
pip install -r requirements.txt
python step.py            # advance the chain one frame (no-op if today has one)
python step.py --force    # ...even if today already has one
python step.py --render   # rebuild the site from existing data, no API calls
python -m pytest tests/ -q
```

Needs `GEMINI_API_KEY`, `CF_ACCOUNT_ID` and `CF_API_TOKEN`, from a gitignored
`.env` locally or from repository secrets in CI. Both services are on free tiers.

## Data

- `data/frames/NNNN.json` - one file per frame, holding its description, prompt,
  image path, perceptual hash and movement reading. A frame never changes once
  written, so it never appears in another diff.
- `assets/img/fNNNN.jpg` - the frames, all one width. Not decorative: the
  movement reading compares them against each other, so a size change mid-chain
  would register as movement the loop did not produce.
- `manifest.json` - the whole chain as data, rebuilt each run. The page does not
  read it (the payload is inlined so the viewer works on first paint); it is
  there for anyone who wants the chain without scraping it.

## The site

One page. Two buttons and the left/right keys step through the chain a frame at
a time, Home and End jump to the ends, and the URL hash (`#f14`) makes any frame
linkable. No slider: the whole value is in comparing one frame with the next, and
a scrubber invites skimming past exactly that.

The six captured slots are shown as one caption rather than a labelled form. The
anomaly clause comes last in the accent colour: it is the slot that decides which
detail survives into the next frame, so it is worth seeing, but "anomaly" is a
word from the pipeline and means nothing to a reader looking at a picture.

A line above the caption says which frame the model was looking at when it wrote
it. This is load-bearing, not decoration: the caption shown with frame N was
written from frame N-1 and is the prompt that DREW frame N. Without the line
every reader takes it as a description of the picture they are looking at, which
is exactly backwards.

Silkscreen sets the chrome - title, frame counter, small print. It is a bitmap
face with no curves, unreadable as running prose, so the caption stays in the
system font. Deliberately not a page per frame: the whole
point is comparing frame N with frame N+1, and a document load between them puts
a white flash exactly where the comparison happens.
