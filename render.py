"""Build the site: one viewer page plus a manifest it reads.

Deliberately NOT a page per frame. The whole point of this project is comparing
frame N with frame N+1, and a full document load between them puts a white flash
exactly where the comparison happens. So: a flat manifest, client-side paging,
and a hash in the URL so any frame is still linkable.
"""
from __future__ import annotations

import html
import json

import chain
from common import BEACON, hyphenate, load_settings, rel, write_json

_CSS = """
:root{
  --bg:#faf9f7; --card:#fff; --fg:#17150f; --muted:#7a7468; --faint:#a8a294;
  --rule:#e3dfd6; --accent:#8a3a1e;
}
@media (prefers-color-scheme:dark){
  :root{--bg:#131211; --card:#1b1a18; --fg:#eceae5; --muted:#9d968a;
        --faint:#6e675c; --rule:#2c2a26; --accent:#d97a55;}
}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--fg);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
  line-height:1.55;-webkit-font-smoothing:antialiased;}
.wrap{max-width:40rem;margin:0 auto;padding:1.25rem 1.25rem 4rem;}
/* Top bar: the way back out comes first, not buried in a footer. */
.top{display:flex;justify-content:space-between;align-items:center;
  margin:0 0 2.25rem;font-size:0.78rem;}
.top a{color:var(--muted);text-decoration:none;}
.top a:hover{color:var(--accent);}
header{margin:0 0 1.5rem;}
h1{font-size:1.6rem;margin:0;font-weight:600;letter-spacing:-0.015em;}
.tag{color:var(--muted);font-size:0.85rem;margin-top:0.25rem;}
.frame{position:relative;aspect-ratio:1/1;overflow:hidden;border-radius:3px;
  background:var(--card);box-shadow:0 1px 2px rgba(0,0,0,0.06),
  0 8px 28px -12px rgba(0,0,0,0.28);}
.frame img{width:100%;height:100%;object-fit:cover;display:block;}
/* Controls sit under the picture so nothing crowds it at any width. */
.controls{display:flex;align-items:center;justify-content:space-between;
  gap:1rem;margin:0.9rem 0 0;}
.nav{flex:0 0 auto;width:2.6rem;height:2.6rem;border:1px solid var(--rule);
  background:var(--card);color:var(--fg);font:inherit;font-size:1rem;
  cursor:pointer;border-radius:50%;line-height:1;transition:.12s ease;}
.nav:hover:not(:disabled){border-color:var(--accent);color:var(--accent);
  transform:translateY(-1px);}
.nav:disabled{opacity:0.28;cursor:default;}
.nav:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
.pos{flex:1 1 auto;text-align:center;min-width:0;}
.pos .where{display:block;font-size:0.9rem;font-weight:600;}
.pos .sub{display:block;font-size:0.7rem;color:var(--faint);margin-top:0.1rem;}
dl.desc{margin:2rem 0 0;padding-top:1.25rem;border-top:1px solid var(--rule);
  display:grid;grid-template-columns:4.5rem 1fr;gap:0.7rem 1rem;}
/* display:contents so dt and dd are themselves grid items - without it each
   wrapper div is one cell, the labels wrap inside a 4.5rem column, and the
   block triples in height. */
dl.desc > div{display:contents;}
dl.desc dt{color:var(--faint);font-size:0.62rem;letter-spacing:0.14em;
  text-transform:uppercase;padding-top:0.28rem;}
dl.desc dd{margin:0;font-size:0.94rem;}
dl.desc dd:empty::after{content:"-";color:var(--faint);}
.anomaly dd{color:var(--accent);}
.note{margin:1.75rem 0 0;padding-top:1.1rem;border-top:1px solid var(--rule);
  color:var(--muted);font-size:0.78rem;}
.note p{margin:0;}
.note a{color:var(--accent);}
@media (max-width:30rem){
  dl.desc{grid-template-columns:1fr;gap:0.1rem;}
  dl.desc dt{padding-top:0.75rem;}
  h1{font-size:1.4rem;}
}
"""

# Raw literal: the regex escape and the middle-dot escape are for JavaScript
# to read, not Python. A non-raw string warns on one and eats the other.
_JS = r"""
(function(){
  var M=window.__PHOTOCOPY__||{frames:[]},F=M.frames,i=F.length-1;
  if(!F.length)return;
  var img=document.getElementById('shot'),prev=document.getElementById('prev'),
      next=document.getElementById('next'),where=document.getElementById('where'),
      sub=document.getElementById('sub');
  var pre=[];
  function warm(k){[k-1,k+1].forEach(function(j){
    if(j<0||j>=F.length)return;var im=new Image();im.src=F[j].image;pre.push(im);
    if(pre.length>8)pre.shift();});}
  function show(k,push){
    i=Math.max(0,Math.min(F.length-1,k));
    var f=F[i];
    img.src=f.image;img.alt=f.alt;
    where.textContent='Frame '+f.frame+' of '+F.length;
    sub.textContent=f.date+(f.text==null?'':
      '  \u00b7  '+Math.round(f.text*100)+'% alike, '
      +Math.round(f.image_distance)+'/64 apart');
    f.fields.forEach(function(v,n){
      document.getElementById('f'+n).textContent=v;});
    prev.disabled=(i===0);next.disabled=(i===F.length-1);
    if(push)history.replaceState(null,'','#f'+f.frame);
    warm(i);
  }
  function jump(d){show(i+d,true);}
  prev.addEventListener('click',function(){jump(-1);});
  next.addEventListener('click',function(){jump(1);});
  document.addEventListener('keydown',function(e){
    if(e.metaKey||e.ctrlKey||e.altKey)return;
    if(e.key==='ArrowLeft'){jump(-1);e.preventDefault();}
    else if(e.key==='ArrowRight'){jump(1);e.preventDefault();}
    else if(e.key==='Home'){show(0,true);e.preventDefault();}
    else if(e.key==='End'){show(F.length-1,true);e.preventDefault();}
  });
  var m=/^#f(\d+)$/.exec(location.hash||'');
  var start=F.length-1;
  if(m){for(var k=0;k<F.length;k++){
    if(F[k].frame===+m[1]){start=k;break;}}}
  show(start,false);
})();
"""


#: How the six captured slots are shown. Subject, setting and materials are one
#: thought - what the thing is and what it is made of - and three separate
#: labelled rows for them made the page read like a form. Pose, light and the
#: anomaly stay on their own: the anomaly in particular is the slot that decides
#: what survives into the next frame, so it should not be buried in a paragraph.
DISPLAY = (
    ("scene", ("subject", "setting", "materials")),
    ("pose", ("posture",)),
    ("light", ("light",)),
    ("anomaly", ("anomaly",)),
)


def _sentence(text: str) -> str:
    """One model clause as a sentence. They arrive uncapitalised and mostly
    unpunctuated, and three of them run together need both to be readable."""
    text = (text or "").strip().rstrip(".")
    if not text:
        return ""
    return text[0].upper() + text[1:] + "."


def group(desc: dict) -> list[str]:
    """The description as the four blocks the page shows."""
    out = []
    for _label, slots in DISPLAY:
        parts = [_sentence(hyphenate(desc.get(slot, ""))) for slot in slots]
        out.append(" ".join(p for p in parts if p))
    return out


def flatten(frames: list[dict]) -> list[dict]:
    """The chain as the viewer wants it."""
    out = []
    for frame in frames:
        desc = frame.get("description", {})
        reading = frame.get("reading") or {}
        out.append({
            "frame": frame["n"],
            "date": frame.get("date", ""),
            "image": frame["image"],
            "alt": (desc.get("subject") or "One frame of the chain")[:180],
            "fields": group(desc),
            "text": reading.get("text"),
            "image_distance": reading.get("image"),
        })
    return out


def render_page(frames_raw: list[dict], meta: dict) -> str:
    frames = flatten(frames_raw)
    rows = "".join(
        '<div{cls}><dt>{name}</dt><dd id="f{i}"></dd></div>'.format(
            cls=' class="anomaly"' if name == "anomaly" else "", name=name, i=i)
        for i, (name, _slots) in enumerate(DISPLAY))
    payload = json.dumps({"frames": frames}, ensure_ascii=False)
    empty = "" if frames else (
        '<p class="note">The chain has not started yet. The first frame is drawn '
        'from a written seed; every frame after it comes only from a description '
        'of the one before.</p>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#f2f1ee">
<title>{html.escape(meta['site_name'])}</title>
<meta property="og:type" content="website">
<meta property="og:site_name" content="{html.escape(meta['site_name'])}">
<meta property="og:title" content="{html.escape(meta['site_name'])}">
<meta property="og:description" content="{html.escape(meta['tagline'])}">
<style>{_CSS}</style>
{BEACON}
</head>
<body>
  <div class="wrap">
    <nav class="top">
      <a href="https://charlietrenorden.com/">&larr; Other Projects</a>
      <a href="https://github.com/charlie-tren/photocopy">Source</a>
    </nav>
    <header>
      <h1>{html.escape(meta['site_name'])}</h1>
      <div class="tag">{html.escape(meta['tagline'])}</div>
    </header>
    {empty}
    <div class="frame"><img id="shot" alt=""></div>
    <div class="controls">
      <button class="nav" id="prev" type="button" aria-label="Previous frame"
              aria-keyshortcuts="ArrowLeft">&larr;</button>
      <div class="pos">
        <span class="where" id="where"></span>
        <span class="sub" id="sub"></span>
      </div>
      <button class="nav" id="next" type="button" aria-label="Next frame"
              aria-keyshortcuts="ArrowRight">&rarr;</button>
    </div>
    <dl class="desc">{rows}</dl>
    <div class="note">
      <p>A vision model is shown yesterday's picture and nothing else. What it
      writes above is the entire prompt for today's. The chain is never reset.
      <a href="https://github.com/charlie-tren/photocopy/blob/main/docs/collapse.md">Why
      that is harder than it sounds</a>.</p>
    </div>
  </div>
  <script>window.__PHOTOCOPY__={payload};</script>
  <script>{_JS}</script>
</body>
</html>
"""


def build() -> str:
    settings = load_settings()
    frames = chain.load_frames()
    meta = {"site_name": settings["site"]["name"],
            "tagline": settings["site"]["tagline"]}
    # The manifest is not read by the page (the payload is inlined, so the viewer
    # works on first paint with no second request). It is written for anyone who
    # wants the chain as data.
    write_json("manifest.json", {"seed": settings["seed"],
                                 "frames": flatten(frames)})
    out = rel(settings["output_html"])
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(render_page(frames, meta))
    return out


if __name__ == "__main__":
    print(f"Wrote {build()}")
