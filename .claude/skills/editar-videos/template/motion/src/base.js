// Shared runtime for the motion graphics.
// ?bg=1 paints the brand background (otherwise transparent, for overlays).
// ?c=1.2,3.4,... cue times in seconds (synced to the voice-over); pages read them with cue(i, default).
// Other params: num(k, default), str(k, default); rich(text) for display text with *accent* and | breaks.
// window.__seek(ms) freezes every animation at that point, so the renderer can capture frame by frame.
// tick(fn): fn(t) gets the page time in seconds, on every frame when previewing live and on every __seek when
// rendering. Use it for what CSS can't animate (counters, timers); fn must depend only on t.
const params = new URLSearchParams(location.search);
if (params.get('bg') === '1') document.body.classList.add('opaque');
const CUES = (params.get('c') || '').split(',').filter((s) => s !== '').map(Number);
window.cue = (i, d) => (CUES[i] !== undefined && !Number.isNaN(CUES[i]) ? CUES[i] : d);
window.anim = (el, value) => { el.style.animation = value; };
window.num = (k, d) => { const v = params.get(k); return v === null || v === '' || Number.isNaN(Number(v)) ? d : Number(v); };
window.str = (k, d) => { const v = params.get(k); return v === null || v === '' ? d : v; };
window.clamp01 = (x) => Math.min(1, Math.max(0, x));
window.easeOut = (x) => 1 - Math.pow(1 - clamp01(x), 3);
window.prog = (t, start, dur) => clamp01((t - start) / dur);
window.$ = (id) => document.getElementById(id);
// rich(text): escapes HTML; *words* = accent colour (.hl), | = line break. For text passed in the query string.
window.rich = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))
  .replace(/\*([^*]+)\*/g, '<span class="hl">$1</span>').replace(/\|/g, '<br>');
const __ticks = [];
let __live = true;
const __t0 = performance.now();
window.tick = (fn) => { __ticks.push(fn); fn(0); };
(function __loop() {
  if (!__live) return;
  const t = (performance.now() - __t0) / 1000;
  __ticks.forEach((f) => f(t));
  requestAnimationFrame(__loop);
})();
window.__seek = (ms) => {
  __live = false;
  document.getAnimations().forEach((a) => { a.pause(); a.currentTime = ms; });
  __ticks.forEach((f) => f(ms / 1000));
};
