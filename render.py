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
from describe import FIELDS

_CSS = """
:root{--bg:#f2f1ee;--fg:#16150f;--muted:#6f6b60;--rule:#d6d2c7;--accent:#8a3a1e;}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--fg);
  font-family:-apple-system,system-ui,'Segoe UI',sans-serif;line-height:1.5;}
.wrap{max-width:54rem;margin:0 auto;padding:clamp(1.5rem,5vw,3rem) 1.25rem 4rem;}
header{border-bottom:1px solid var(--fg);padding-bottom:0.8rem;margin-bottom:1.6rem;}
h1{font-size:clamp(1.5rem,5vw,2.1rem);margin:0;font-weight:600;letter-spacing:-0.01em;}
.tag{color:var(--muted);font-size:0.82rem;margin-top:0.3rem;}
.stage{display:flex;align-items:center;gap:0.75rem;}
.frame{flex:1 1 auto;min-width:0;position:relative;background:#e6e4df;
  aspect-ratio:1/1;overflow:hidden;}
.frame img{width:100%;height:100%;object-fit:cover;display:block;}
.nav{flex:0 0 auto;width:3rem;height:3rem;border:1px solid var(--rule);
  background:transparent;color:var(--fg);font:inherit;font-size:1.2rem;
  cursor:pointer;border-radius:50%;}
.nav:hover:not(:disabled){border-color:var(--accent);color:var(--accent);}
.nav:disabled{opacity:0.25;cursor:default;}
.rowmeta{display:flex;flex-wrap:wrap;gap:0.5rem 1.2rem;align-items:baseline;
  margin:0.9rem 0 0;font-size:0.8rem;color:var(--muted);}
.rowmeta .where{color:var(--fg);font-weight:600;font-size:0.95rem;}

.scrub{width:100%;margin:0.9rem 0 0;accent-color:var(--accent);}
dl.desc{margin:1.6rem 0 0;padding-top:1rem;border-top:1px solid var(--rule);
  display:grid;grid-template-columns:7.5rem 1fr;gap:0.55rem 1.2rem;}
dl.desc dt{color:var(--muted);font-size:0.68rem;letter-spacing:0.12em;
  text-transform:uppercase;padding-top:0.15rem;}
dl.desc dd{margin:0;font-size:0.98rem;}
dl.desc dd:empty::after{content:"-";color:var(--muted);}
.anomaly dd{color:var(--accent);}
.note{margin:1.6rem 0 0;padding-top:1rem;border-top:1px solid var(--rule);
  color:var(--muted);font-size:0.82rem;}
.note p{margin:0 0 0.6rem;}
.runs{margin:0.8rem 0 0;font-size:0.78rem;color:var(--muted);}
.runs b{color:var(--fg);}
a{color:var(--accent);}
footer{margin-top:2.4rem;padding-top:1rem;border-top:1px solid var(--rule);
  font-size:0.78rem;color:var(--muted);}
@media (max-width:34rem){
  dl.desc{grid-template-columns:1fr;gap:0.15rem;}
  dl.desc dt{padding-top:0.5rem;}
  /* Arrows drop beneath the picture rather than flanking it. Side-by-side they
     cost 100px of a 375px screen, which is a quarter of the only thing on the
     page worth looking at. */
  .stage{display:grid;gap:0.5rem;grid-template-columns:1fr 1fr;
    grid-template-areas:"img img" "prev next";}
  .frame{grid-area:img;}
  #prev{grid-area:prev;}
  #next{grid-area:next;}
  .nav{width:100%;height:2.75rem;border-radius:1.4rem;}
}
"""

_JS = """
(function(){
  var M=window.__PHOTOCOPY__||{frames:[]},F=M.frames,i=F.length-1;
  if(!F.length)return;
  var img=document.getElementById('shot'),prev=document.getElementById('prev'),
      next=document.getElementById('next'),scrub=document.getElementById('scrub'),
      where=document.getElementById('where'),when=document.getElementById('when'),
      state=document.getElementById('state');
  scrub.max=F.length-1;
  var pre=[];
  function warm(k){[k-1,k+1].forEach(function(j){
    if(j<0||j>=F.length)return;var im=new Image();im.src=F[j].image;pre.push(im);
    if(pre.length>8)pre.shift();});}
  function show(k,push){
    i=Math.max(0,Math.min(F.length-1,k));
    var f=F[i];
    img.src=f.image;img.alt=f.alt;
    where.textContent='Frame '+f.frame+' of '+F.length;
    when.textContent=f.date;
    state.textContent=(f.text==null)?'':
      'last 5 frames: '+Math.round(f.text*100)+'% alike in words, '
      +Math.round(f.image_distance)+'/64 apart in pixels';
    F[i].fields.forEach(function(v,n){
      document.getElementById('f'+n).textContent=v;});
    scrub.value=i;
    prev.disabled=(i===0);next.disabled=(i===F.length-1);
    if(push)history.replaceState(null,'','#f'+f.frame);
    warm(i);
  }
  function jump(d){show(i+d,true);}
  prev.addEventListener('click',function(){jump(-1);});
  next.addEventListener('click',function(){jump(1);});
  scrub.addEventListener('input',function(){show(parseInt(scrub.value,10),true);});
  document.addEventListener('keydown',function(e){
    if(e.metaKey||e.ctrlKey||e.altKey)return;
    if(e.key==='ArrowLeft'){jump(-1);e.preventDefault();}
    else if(e.key==='ArrowRight'){jump(1);e.preventDefault();}
    else if(e.key==='Home'){show(0,true);e.preventDefault();}
    else if(e.key==='End'){show(F.length-1,true);e.preventDefault();}
  });
  var m=/^#f(\\d+)$/.exec(location.hash||'');
  var start=F.length-1;
  if(m){for(var k=0;k<F.length;k++){
    if(F[k].frame===+m[1]){start=k;break;}}}
  show(start,false);
})();
"""


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
            "fields": [hyphenate(desc.get(f, "")) for f in FIELDS],
            "text": reading.get("text"),
            "image_distance": reading.get("image"),
        })
    return out


def _movement_line(frames: list[dict]) -> str:
    """The two numbers, in words. Reported, never acted on."""
    if len(frames) < 2:
        return "Not enough frames yet to say whether the chain is moving."
    reading = frames[-1].get("reading") or {}
    text, dist = reading.get("text"), reading.get("image")
    if text is None or dist is None:
        return ""
    return (f"Across the last {reading.get('n', 0)} frames the descriptions are "
            f"<b>{text:.0%}</b> alike and the pictures differ by <b>{dist:.0f}</b> "
            "of a possible 64.")


def render_page(frames_raw: list[dict], meta: dict) -> str:
    frames = flatten(frames_raw)
    rows = "".join(
        '<div{cls}><dt>{name}</dt><dd id="f{i}"></dd></div>'.format(
            cls=' class="anomaly"' if name == "anomaly" else "", name=name, i=i)
        for i, name in enumerate(FIELDS))
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
    <header>
      <h1>{html.escape(meta['site_name'])}</h1>
      <div class="tag">{html.escape(meta['tagline'])}</div>
    </header>
    {empty}
    <div class="stage">
      <button class="nav" id="prev" type="button" aria-label="Previous frame"
              aria-keyshortcuts="ArrowLeft">&larr;</button>
      <div class="frame"><img id="shot" alt=""></div>
      <button class="nav" id="next" type="button" aria-label="Next frame"
              aria-keyshortcuts="ArrowRight">&rarr;</button>
    </div>
    <!-- autocomplete=off is load-bearing: without it the browser restores the
         slider's value from the previous visit AFTER the script has run, which
         fires input and quietly overrides the frame named in the URL hash. -->
    <input class="scrub" id="scrub" type="range" min="0" value="0" step="1"
           autocomplete="off" aria-label="Scrub through the chain">
    <div class="rowmeta">
      <span class="where" id="where"></span>
      <span id="when"></span>
      <span id="state"></span>
    </div>
    <dl class="desc">{rows}</dl>
    <div class="note">
      <p>Each morning a vision model is shown yesterday's photograph and nothing
      else - no earlier picture, no earlier words, no idea what it is looking at.
      It fills in the six slots above. Those six lines are the entire prompt for
      today's photograph. Then it is shown that one, and so on.</p>
      <p>Loops like this are known to converge rather than wander: left alone
      they settle into a stock scene and stay there. Two rules push back, and
      both are generated from the chain's own past rather than supplied from
      outside - the fixed slots, which stop the description dissolving into
      atmosphere, and a ban on whatever words the chain has leaned on lately.
      Nothing else intervenes. There is one chain, it started once, and it is
      never reset.</p>
      <p class="runs">{_movement_line(frames_raw)}</p>
    </div>
    <footer>
      Every image is machine-made and depicts nothing that exists.
      <a href="https://charlietrenorden.com/">&larr; Other Projects</a>
    </footer>
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
