/** Sound: every effect and the ambience are synthesized with Web Audio (no audio files).
 *
 * Two halves:
 * - `soundEvents(prev, next, surfaceAt)` is pure: it compares two snapshots and names
 *   what was heard (a step on grass, a thrust, a hit, loot, a level...). Tested in node.
 * - `SoundEngine` turns names into short synth patches and keeps a quiet ambience bed
 *   (wind, birds, the river when water is near, fire crackle beside a fire).
 * Cosmetic only: Math.random here never touches the simulation. The context starts on
 * the first key or pointer press (browser autoplay rules); a hidden tab suspends it. */

export const SOUND_KEY = 'dimsum.sound';
export const VOLUMES = Object.freeze([['Off', 0], ['Low', .35], ['Medium', .65], ['High', 1]]);
export const DEFAULT_SETTINGS = Object.freeze({volume: 2, ambience: true});

export function loadSettings(raw) {
  try {
    const v = JSON.parse(raw || 'null');
    if (v && Number.isInteger(v.volume) && v.volume >= 0 && v.volume < VOLUMES.length && typeof v.ambience === 'boolean')
      return {volume: v.volume, ambience: v.ambience};
  } catch { /* fall through */ }
  return {...DEFAULT_SETTINGS};
}

/** What a tile sounds like underfoot. */
export function surfaceOf(glyph) {
  if (glyph === 'w' || glyph === '%') return 'water';
  if (glyph === 'H') return 'wood';
  if (glyph === 'F' || glyph === '^' || glyph === 'M' || glyph === 'P' || glyph === 'Q' || glyph === 'I') return 'stone';
  if (glyph === '=' || glyph === ':' || glyph === 'x') return 'dirt';
  return 'grass';
}

/** Rhythm of work sounds per activity kind: [sound, interval ms] (none: silent work). */
export const WORK = Object.freeze({
  gather: ['chop', 620], scavenge: ['rustle', 900], forage: ['rustle', 1100], hunt: ['rustle', 1300],
  craft: ['tap', 520], build: ['thunk', 700], camp: ['rustle', 800], climb: ['scrape', 900],
  drink: ['sip', 1400], study: ['page', 2200], observe: ['page', 2600]});

const levels = ex => Object.values(ex?.attributes || {}).reduce((sum, row) => sum + (row.level || 0), 0);

/** Sounds heard between two snapshots: [{name, ...}] (pure). */
export function soundEvents(prev, next, surfaceAt = () => 'grass') {
  if (!prev || !next) return [];
  const out = [], pe = prev.expedition, ne = next.expedition;
  if (pe && ne && ne.life !== pe.life) return [{name: 'death'}];
  if (ne?.anchor_space && !pe?.anchor_space) out.push({name: 'anchor'});
  const p0 = prev.player, p1 = next.player;
  if (p1.x !== p0.x || p1.y !== p0.y) out.push({name: 'step', surface: surfaceAt(p1.x, p1.y)});
  if (p1.animation === 'attack' && (p0.animation !== 'attack' || p1.animation_ms < p0.animation_ms))
    out.push({name: 'swing', shape: ne?.weapon?.shape || 'punch'});
  const before = new Map(prev.targets.map(t => [t.id, t]));
  for (const t of next.targets) {
    const old = before.get(t.id);
    if (!old) continue;
    if (t.hp < old.hp) out.push({name: t.hp === 0 ? 'kill' : 'hit', sprite: t.sprite});
    if ((t.strikes || 0) > (old.strikes || 0)) out.push({name: 'hurt', sprite: t.sprite});
  }
  if (pe && ne) {
    const seq = Math.max(0, ...(pe.log || []).map(e => e.seq));
    for (const e of (ne.log || []).filter(e => e.seq > seq)) {
      if (e.type === 'ambush') out.push({name: 'ambush'});
      else if (e.type === 'eat') out.push({name: 'eat'});
      else if (e.type === 'craft') out.push({name: 'crafted'});
      else if (e.type === 'build') out.push({name: 'built'});
      else if (e.type === 'blessing') out.push({name: 'blessing'});
      const gained = (e.items || []).filter(([, n]) => n > 0).map(([item]) => item);
      const rare = gained.find(item => ne.item_glints?.[item]);
      if (rare) out.push({name: 'rare'});
      else if (gained.length && e.type !== 'eat') out.push({name: 'loot'});
    }
    if (levels(ne) > levels(pe)) out.push({name: 'level'});
    if (ne.campfire && !pe.campfire) out.push({name: 'kindle'});
    if (ne.region?.shimmer && !pe.region?.shimmer) out.push({name: 'shimmer'});
  }
  return out;
}

// --- synthesis -------------------------------------------------------------------
export class SoundEngine {
  constructor({AudioContextClass = globalThis.AudioContext || globalThis.webkitAudioContext, settings = DEFAULT_SETTINGS,
    random = Math.random} = {}) {
    this.AudioContextClass = AudioContextClass;
    this.settings = {...settings};
    this.random = random;
    this.ctx = null;
    this.workAt = 0;
    this.nextBird = 0;
    this.nextCrackle = 0;
  }
  get volume() { return VOLUMES[this.settings.volume][1]; }
  get label() { return VOLUMES[this.settings.volume][0]; }
  /** Create (or resume) the audio context; call from a user gesture. */
  unlock() {
    if (!this.AudioContextClass || this.volume === 0) return;
    if (!this.ctx) this.build();
    if (this.ctx.state === 'suspended') this.ctx.resume?.();
  }
  build() {
    const c = this.ctx = new this.AudioContextClass();
    this.master = c.createGain(); this.master.gain.value = this.volume; this.master.connect(c.destination);
    this.sfx = c.createGain(); this.sfx.gain.value = .8; this.sfx.connect(this.master);
    this.amb = c.createGain(); this.amb.gain.value = this.settings.ambience ? 1 : 0; this.amb.connect(this.master);
    const len = c.sampleRate | 0, buffer = c.createBuffer(1, len, c.sampleRate), data = buffer.getChannelData(0);
    for (let i = 0; i < len; i++) data[i] = this.random() * 2 - 1;
    this.noise = buffer;
    // ambience beds: wind (low band, slow swell) and river (wider band), both looping noise
    this.wind = this.bed(380, .6, 'bandpass');
    this.river = this.bed(900, .5, 'lowpass');
    this.fireBed = this.bed(260, .8, 'lowpass');
    const lfo = c.createOscillator(), depth = c.createGain();
    lfo.frequency.value = .07; depth.gain.value = .015;
    lfo.connect(depth); depth.connect(this.wind.gain.gain); lfo.start();
  }
  bed(freq, q, type) {
    const c = this.ctx, src = c.createBufferSource(), filter = c.createBiquadFilter(), gain = c.createGain();
    src.buffer = this.noise; src.loop = true;
    filter.type = type; filter.frequency.value = freq; filter.Q.value = q;
    gain.gain.value = 0;
    src.connect(filter); filter.connect(gain); gain.connect(this.amb); src.start();
    return {gain, filter};
  }
  apply(settings) {
    this.settings = {...settings};
    if (this.volume > 0) this.unlock();
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    this.master.gain.setTargetAtTime(this.volume, t, .05);
    this.amb.gain.setTargetAtTime(this.settings.ambience ? 1 : 0, t, .3);
  }
  suspend(hidden) {
    if (!this.ctx) return;
    if (hidden) this.ctx.suspend?.(); else this.ctx.resume?.();
  }
  get live() { return !!this.ctx && this.volume > 0 && this.ctx.state !== 'suspended'; }

  // primitives -------------------------------------------------------------------
  env(param, t, peak, attack, dur) {
    param.setValueAtTime(0.0001, t);
    param.linearRampToValueAtTime(peak, t + attack);
    param.exponentialRampToValueAtTime(0.0001, t + dur);
  }
  tone({type = 'sine', freq = 440, to = null, dur = .12, gain = .2, attack = .005, delay = 0, bus = this.sfx}) {
    const c = this.ctx, t = c.currentTime + delay, o = c.createOscillator(), g = c.createGain();
    o.type = type; o.frequency.setValueAtTime(freq, t);
    if (to) o.frequency.exponentialRampToValueAtTime(to, t + dur);
    this.env(g.gain, t, gain, attack, dur);
    o.connect(g); g.connect(bus); o.start(t); o.stop(t + dur + .05);
  }
  burst({type = 'bandpass', freq = 1200, to = null, q = 1, dur = .08, gain = .2, attack = .004, delay = 0, bus = this.sfx}) {
    const c = this.ctx, t = c.currentTime + delay, s = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain();
    s.buffer = this.noise;
    f.type = type; f.Q.value = q; f.frequency.setValueAtTime(freq, t);
    if (to) f.frequency.exponentialRampToValueAtTime(to, t + dur);
    this.env(g.gain, t, gain, attack, dur);
    s.connect(f); f.connect(g); g.connect(bus);
    s.start(t, this.random() * .5); s.stop(t + dur + .05);
  }
  notes(freqs, {type = 'triangle', step = .08, dur = .16, gain = .12, delay = 0} = {}) {
    freqs.forEach((freq, i) => this.tone({type, freq, dur, gain, delay: delay + i * step}));
  }

  // patches -------------------------------------------------------------------------
  play(event) {
    if (!this.live) return;
    const r = this.random, name = event.name ?? event;
    const PATCH = {
      step: () => {
        const s = event.surface;
        if (s === 'water') { this.burst({type: 'bandpass', freq: 900, to: 350, q: 1.2, dur: .16, gain: .16}); this.tone({freq: 500 + r() * 200, to: 900, dur: .06, gain: .03, delay: .04}); }
        else if (s === 'wood') { this.tone({type: 'triangle', freq: 190 + r() * 30, dur: .06, gain: .1}); this.burst({freq: 1400, dur: .03, gain: .05}); }
        else if (s === 'stone') { this.tone({type: 'square', freq: 900 + r() * 200, dur: .02, gain: .025}); this.burst({type: 'highpass', freq: 3000, dur: .03, gain: .04}); }
        else if (s === 'dirt') { this.burst({freq: 1300 + r() * 400, q: .8, dur: .05, gain: .14}); this.burst({freq: 2200, q: .8, dur: .03, gain: .08, delay: .03}); }
        else this.burst({type: 'highpass', freq: 2600 + r() * 1200, q: .5, dur: .07, gain: .045});
      },
      swing: () => {
        if (event.shape === 'thrust') { this.burst({freq: 900, to: 3200, q: 2, dur: .13, gain: .45}); this.tone({type: 'square', freq: 1800, dur: .015, gain: .02, delay: .11}); }
        else if (event.shape === 'swing') this.burst({freq: 450, to: 1600, q: 1.6, dur: .24, gain: .5, attack: .06});
        else { this.burst({type: 'lowpass', freq: 900, dur: .06, gain: .12}); this.tone({freq: 150, to: 80, dur: .07, gain: .08}); }
      },
      hit: () => { this.tone({freq: 190, to: 60, dur: .14, gain: .3}); this.burst({type: 'lowpass', freq: 2400, dur: .05, gain: .2}); this.rattle(event.sprite, 3); },
      kill: () => { this.rattle(event.sprite, 7); this.tone({type: 'sawtooth', freq: 260, to: 70, dur: .45, gain: .08}); this.burst({type: 'lowpass', freq: 700, to: 200, dur: .5, gain: .12}); this.tone({freq: 120, to: 50, dur: .2, gain: .3}); },
      hurt: () => {
        if (event.sprite === 'wisp') {   // it feeds rather than bites: a cold, falling chime
          this.tone({freq: 1320, to: 660, dur: .5, gain: .06, attack: .02}); this.tone({freq: 1328, to: 664, dur: .5, gain: .05, attack: .03});
          return;
        }
        this.tone({freq: 95, to: 45, dur: .22, gain: .35}); this.burst({type: 'lowpass', freq: 600, dur: .14, gain: .2}); },
      ambush: () => { this.tone({type: 'sawtooth', freq: 110, to: 98, dur: .6, gain: .06, attack: .02}); this.tone({type: 'sawtooth', freq: 116.5, to: 104, dur: .6, gain: .06, attack: .02}); this.burst({type: 'lowpass', freq: 400, dur: .5, gain: .08}); },
      loot: () => this.notes([660 + r() * 4, 990], {step: .07, dur: .12, gain: .12}),
      rare: () => this.notes([523, 659, 784, 1047, 1319], {step: .07, dur: .3, gain: .09}),
      level: () => { this.notes([392, 523, 659, 784], {step: .09, dur: .5, gain: .08}); this.tone({freq: 1568, dur: .8, gain: .02, delay: .36, attack: .05}); },
      eat: () => { for (let i = 0; i < 3; i++) this.burst({freq: 1600 + r() * 800, q: 2, dur: .05, gain: .3, delay: i * .11}); },
      crafted: () => { this.tone({type: 'triangle', freq: 440, to: 660, dur: .18, gain: .1}); this.tone({type: 'square', freq: 1320, dur: .03, gain: .02, delay: .17}); },
      built: () => { for (let i = 0; i < 3; i++) { this.tone({type: 'triangle', freq: 140, to: 90, dur: .1, gain: .18, delay: i * .16}); this.burst({type: 'lowpass', freq: 1200, dur: .05, gain: .08, delay: i * .16}); } },
      blessing: () => { this.tone({freq: 392, dur: 1.6, gain: .06, attack: .4}); this.tone({freq: 587, dur: 1.6, gain: .05, attack: .5}); this.tone({freq: 784, dur: 1.4, gain: .03, attack: .6, delay: .2}); },
      kindle: () => { this.burst({type: 'highpass', freq: 1800, dur: .4, gain: .08, attack: .1}); for (let i = 0; i < 5; i++) this.burst({freq: 2500 + r() * 2000, q: 3, dur: .02, gain: .08, delay: .1 + r() * .5}); },
      death: () => { this.tone({freq: 330, to: 82, dur: 1.6, gain: .12, attack: .05}); this.tone({type: 'triangle', freq: 247, to: 62, dur: 1.8, gain: .06, attack: .1}); this.burst({type: 'lowpass', freq: 500, to: 120, dur: 1.4, gain: .08}); },
      shimmer: () => { this.tone({freq: 466, to: 440, dur: 2.2, gain: .05, attack: .6}); this.tone({freq: 470, to: 446, dur: 2.2, gain: .05, attack: .7});
        this.notes([1760, 1661, 1976], {type: 'sine', step: .3, dur: .9, gain: .015, delay: .4}); },
      anchor: () => { this.notes([294, 440, 587], {type: 'sine', step: .18, dur: 1.2, gain: .06}); },
      chop: () => { this.tone({type: 'triangle', freq: 170 + r() * 20, to: 110, dur: .08, gain: .22}); this.burst({freq: 1800, q: 1.5, dur: .05, gain: .12}); },
      rustle: () => this.burst({freq: 3000 + r() * 1500, q: .7, dur: .22 + r() * .15, gain: .12, attack: .06}),
      tap: () => { this.tone({type: 'square', freq: 620 + r() * 60, dur: .02, gain: .04}); this.tone({type: 'triangle', freq: 880, dur: .04, gain: .05, delay: .02}); },
      thunk: () => { this.tone({type: 'triangle', freq: 130, to: 85, dur: .1, gain: .2}); this.burst({type: 'lowpass', freq: 1000, dur: .05, gain: .08}); },
      scrape: () => this.burst({freq: 700, to: 1400, q: 3, dur: .2, gain: .25, attack: .05}),
      sip: () => { this.tone({freq: 400, to: 800, dur: .05, gain: .05}); this.tone({freq: 350, to: 700, dur: .05, gain: .04, delay: .12}); },
      page: () => this.burst({type: 'highpass', freq: 3500, dur: .1, gain: .06, attack: .03}),
      click: () => this.tone({freq: 1200, dur: .02, gain: .035}),
      tab: () => { this.tone({freq: 880, dur: .03, gain: .035}); this.tone({freq: 1320, dur: .03, gain: .02, delay: .025}); },
    };
    PATCH[name]?.();
  }

  /** Bones clatter: a run of dry clicks (only for skeleton-like enemies). */
  rattle(sprite, n) {
    if (sprite !== 'skeleton') return;
    for (let i = 0; i < n; i++)
      this.tone({type: 'square', freq: 900 + this.random() * 900, dur: .018, gain: .05, delay: .03 + i * (.035 + this.random() * .03)});
  }

  /** Per-frame upkeep: work rhythm, ambience levels, birds and fire crackle.
   * scene: {now (ms), paused, work (activity kind or null), water (0..1), fire (0..1), outdoors}. */
  update(scene) {
    if (!this.live) return;
    const t = this.ctx.currentTime, now = scene.now, quiet = scene.paused || !scene.outdoors;
    const work = !scene.paused && WORK[scene.work];
    if (work && now >= this.workAt) { this.play(work[0]); this.workAt = now + work[1] * (.85 + this.random() * .3); }
    if (!work) this.workAt = now + 250;
    this.wind.gain.gain.setTargetAtTime(quiet ? .006 : .035, t, .8);
    this.river.gain.gain.setTargetAtTime(quiet ? 0 : .07 * scene.water, t, .6);
    this.fireBed.gain.gain.setTargetAtTime(scene.paused ? 0 : .05 * scene.fire, t, .4);
    if (!quiet && this.settings.ambience && now >= this.nextBird) {
      if (this.nextBird) this.bird();
      this.nextBird = now + 3500 + this.random() * 7000;
    }
    if (!scene.paused && scene.fire > 0 && this.settings.ambience && now >= this.nextCrackle) {
      this.burst({freq: 2000 + this.random() * 3000, q: 4, dur: .015 + this.random() * .02, gain: .06 * scene.fire, bus: this.amb});
      this.nextCrackle = now + 60 + this.random() * 400;
    }
  }
  bird() {
    const r = this.random, base = 2200 + r() * 1600, n = 2 + Math.floor(r() * 4), vol = .02 + r() * .03;
    for (let i = 0; i < n; i++)
      this.tone({freq: base * (1 + r() * .1), to: base * (1.25 + r() * .3), dur: .07 + r() * .05, gain: vol, delay: i * (.1 + r() * .06), bus: this.amb});
  }
}
