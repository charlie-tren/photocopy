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
/* Silkscreen for the chrome only: title, frame counter, small print. It is a
   bitmap face drawn on a pixel grid, so it has no curves and only looks right
   where the grid lands on whole pixels - which also makes it unreadable as
   running prose, hence the description below stays in the system font.
   Self-hosted, SIL OFL, see assets/fonts/README.md. */
@font-face{font-family:'Silkscreen';font-style:normal;font-weight:400;
  font-display:swap;src:url(assets/fonts/silkscreen-400-latin.woff2) format('woff2');
  unicode-range:U+0000-00FF,U+2018-201A,U+201C-201E,U+2022,U+2026,U+2039-203A;}
@font-face{font-family:'Silkscreen';font-style:normal;font-weight:700;
  font-display:swap;src:url(assets/fonts/silkscreen-700-latin.woff2) format('woff2');
  unicode-range:U+0000-00FF,U+2018-201A,U+201C-201E,U+2022,U+2026,U+2039-203A;}
/* --muted and --faint both carry real text, including the provenance line and
   the frame counter, which are 9-10px bitmap type. Both therefore clear WCAG AA
   (4.5:1) against their own background, measured, not eyeballed:
   light  muted 6.33  faint 4.68   dark  muted 6.38  faint 4.98
   The earlier values were 4.41/2.42 on light and 6.38/3.35 on dark, so the
   small print was failing in both themes and badly in light. */
:root{
  --bg:#faf9f7; --card:#fff; --fg:#17150f; --muted:#615c50; --faint:#767061;
  --rule:#e3dfd6; --accent:#8a3a1e;
}
@media (prefers-color-scheme:dark){
  :root{--bg:#131211; --card:#1b1a18; --fg:#eceae5; --muted:#9d968a;
        --faint:#8a8377; --rule:#2c2a26; --accent:#d97a55;}
}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--fg);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
  line-height:1.55;-webkit-font-smoothing:antialiased;}
.wrap{max-width:40rem;margin:0 auto;padding:1.25rem 1.25rem 4rem;}
header{margin:0 0 1.5rem;}
/* Title and the way back out share a line, baseline-aligned, so the name is
   the first thing on the page and the exit is not buried in a footer. */
/* wrap, not nowrap: the title and the link sit on one line wherever there is
   room, and the link drops beneath rather than pushing the page sideways on a
   narrow phone. Silkscreen has no narrow cut to fall back on. */
.titlerow{display:flex;justify-content:space-between;align-items:baseline;
  gap:0.5rem 1rem;flex-wrap:wrap;}
h1{font-family:'Silkscreen',monospace;font-size:2.3rem;margin:0;
  font-weight:700;letter-spacing:0.01em;line-height:1.1;}
.back{flex:0 0 auto;font-family:'Silkscreen',monospace;font-size:0.78rem;
  color:var(--muted);text-decoration:none;white-space:nowrap;}
.back:hover{color:var(--accent);}
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
.pos .where{display:block;font-family:'Silkscreen',monospace;font-size:0.8rem;
  font-weight:700;}
.pos .sub{display:block;font-family:'Silkscreen',monospace;font-size:0.6rem;
  color:var(--faint);margin-top:0.3rem;}
/* One caption, not a labelled form. The six captured slots read as a single
   paragraph, undifferentiated - the anomaly is the last clause and nothing
   marks it out. It is a pipeline word, and colouring it invited the question
   of what the colour meant. */
.info{font-family:'Silkscreen',monospace;font-size:0.55rem;line-height:1;
  margin-left:0.45rem;width:1.05rem;height:1.05rem;padding:0;cursor:pointer;
  border:1px solid var(--rule);border-radius:50%;background:transparent;
  color:var(--faint);vertical-align:0.05rem;position:relative;}
/* The dot is 17px, well under the 44px a thumb needs. Grow the hit area
   without growing the mark. */
.info::after{content:"";position:absolute;inset:-14px;}
.info:hover,.info[aria-expanded="true"]{border-color:var(--accent);
  color:var(--accent);}
.infobox{margin:1rem 0 0;padding:0.9rem 1rem;border:1px solid var(--rule);
  border-radius:3px;background:var(--card);color:var(--muted);font-size:0.78rem;}
.infobox p{margin:0 0 0.55rem;}
.infobox p:last-child{margin:0;}
.infobox b{color:var(--fg);font-weight:600;}
/* The caption was written while looking at the PREVIOUS frame - it is the
   prompt that drew this one, not a description of it. Unlabelled, everyone
   reads it the wrong way round. */
.prov{margin:1.75rem 0 0.5rem;padding-top:1.25rem;
  border-top:1px solid var(--rule);font-family:'Silkscreen',monospace;
  font-size:0.58rem;color:var(--faint);line-height:1.5;}
.caption{margin:0;font-size:1rem;line-height:1.6;}
.note{margin:1.75rem 0 0;padding-top:1.1rem;border-top:1px solid var(--rule);
  color:var(--muted);font-size:0.78rem;}
.note p{margin:0;}
.note a{color:var(--accent);}
@media (max-width:30rem){
  .caption{font-size:0.95rem;}
  h1{font-size:1.55rem;}
  .back{font-size:0.68rem;}
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
      sub=document.getElementById('sub'),cap=document.getElementById('cap'),
      anom=document.getElementById('anom'),prov=document.getElementById('prov'),
      info=document.getElementById('info'),box=document.getElementById('infobox');
  var pre=[];
  function warm(k){[k-1,k+1].forEach(function(j){
    if(j<0||j>=F.length)return;var im=new Image();im.src=F[j].image;pre.push(im);
    if(pre.length>8)pre.shift();});}
  function show(k,push){
    i=Math.max(0,Math.min(F.length-1,k));
    var f=F[i];
    img.src=f.image;img.alt=f.alt;
    where.textContent='Frame '+f.frame+' of '+F.length;
    // Frame 1 has no pair to compare against, so there is nothing for the
    // info button to explain and it would sit beside a bare date.
    info.hidden=(f.text==null);
    if(f.text==null&&!box.hasAttribute('hidden')){
      box.setAttribute('hidden','');info.setAttribute('aria-expanded','false');}
    sub.textContent=f.date+(f.text==null?'':
      '  \u00b7  words '+Math.round(f.text*100)+'% shared, pictures '
      +Math.round(f.image_distance)+'/64 different');
    cap.textContent=f.caption;anom.textContent=f.anomaly;
    prov.textContent=(f.from==null)
      ?'Written seed. Nothing before it.'
      :'Description generated from frame '+f.from;
    prev.disabled=(i===0);next.disabled=(i===F.length-1);
    if(push)history.replaceState(null,'','#f'+f.frame);
    warm(i);
  }
  info.addEventListener('click',function(){
    var open=box.hasAttribute('hidden');
    if(open){box.removeAttribute('hidden');}else{box.setAttribute('hidden','');}
    info.setAttribute('aria-expanded',open?'true':'false');});
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


#: The description is shown as one caption, in this order. The anomaly comes
#: last because it is the slot that decides which detail survives into the next
#: frame, but it is not marked out: "anomaly" is a word from the pipeline and
#: means nothing to anyone looking at a picture.
CAPTION_SLOTS = ("subject", "posture", "setting", "light", "materials")
LAST_SLOT = "anomaly"


def _sentence(text: str) -> str:
    """One model clause as a sentence. They arrive uncapitalised and mostly
    unpunctuated, and six of them run together need both to be readable."""
    text = (text or "").strip().rstrip(".")
    if not text:
        return ""
    return text[0].upper() + text[1:] + "."


def caption(desc: dict) -> tuple[str, str]:
    """(the caption, the anomaly clause appended after it)."""
    body = " ".join(
        p for p in (_sentence(hyphenate(desc.get(s, ""))) for s in CAPTION_SLOTS) if p)
    return body, _sentence(hyphenate(desc.get(LAST_SLOT, "")))


def flatten(frames: list[dict]) -> list[dict]:
    """The chain as the viewer wants it."""
    out = []
    for frame in frames:
        desc = frame.get("description", {})
        reading = frame.get("reading") or {}
        body, anom = caption(desc)
        out.append({
            "frame": frame["n"],
            "date": frame.get("date", ""),
            "image": frame["image"],
            "alt": (desc.get("subject") or "One frame of the chain")[:180],
            # Which frame the model was looking at when it wrote this. Frame 1
            # has none: it came from the written seed. Without this the caption
            # reads as a description OF the picture, which is backwards - it is
            # the description that DREW it.
            "from": frame["n"] - 1 if frame["n"] > 1 else None,
            "caption": body,
            "anomaly": anom,
            "text": reading.get("text"),
            "image_distance": reading.get("image"),
        })
    return out


def render_page(frames_raw: list[dict], meta: dict) -> str:
    frames = flatten(frames_raw)
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
      <div class="titlerow">
        <h1>{html.escape(meta['site_name'])}</h1>
        <a class="back" href="https://charlietrenorden.com/">&larr; Other
          Projects</a>
      </div>
      <div class="tag">{html.escape(meta['tagline'])}</div>
    </header>
    {empty}
    <div class="frame"><img id="shot" alt=""></div>
    <div class="controls">
      <button class="nav" id="prev" type="button" aria-label="Previous frame"
              aria-keyshortcuts="ArrowLeft">&larr;</button>
      <div class="pos">
        <span class="where" id="where"></span>
        <span class="sub"><span id="sub"></span><button type="button" id="info"
          class="info" aria-expanded="false" aria-controls="infobox"
          title="How these numbers are worked out">i</button></span>
      </div>
      <button class="nav" id="next" type="button" aria-label="Next frame"
              aria-keyshortcuts="ArrowRight">&rarr;</button>
    </div>
    <div id="infobox" class="infobox" hidden>
      <p><b>words shared</b> is how much the recent descriptions reuse the
      same words.</p>
      <p><b>pictures different</b> is how far apart the recent images are in
      structure. 0 is identical, about 32 is two unrelated pictures.</p>
      <p>Both averaged over the last five frames. Nothing acts on them.</p>
    </div>
    <p class="prov" id="prov"></p>
    <p class="caption"><span id="cap"></span> <span class="anom" id="anom"></span></p>
    <div class="note">
      <p>The model only ever sees the previous picture. Its description becomes
      the next prompt. Nothing else carries over.</p>
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
