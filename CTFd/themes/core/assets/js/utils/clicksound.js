// The site's sounds, synthesised with Web Audio so there is no file to load:
// - "Retro arcade" click for the 3D push buttons: a quick 8-bit chirp down, a short blip up
// - flag results: "Level up" for a correct flag, "Wrong door" for a wrong one

const BUTTONS =
  ".btn-3d, .auth-submit, .challenge-submit, .crew-link, .hero-actions .btn";
const VOLUME = 0.6;

let ctx = null;
function audio() {
  if (!ctx) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    ctx = new Ctx();
  }
  if (ctx.state === "suspended") ctx.resume();
  return ctx;
}

function chirp(f0, f1, dur, gain, at = 0, type = "square", detune = 0, lowpass = 0) {
  const a = audio();
  if (!a) return;
  const t = a.currentTime + at;
  const osc = a.createOscillator();
  const amp = a.createGain();
  osc.type = type;
  osc.detune.value = detune;
  osc.frequency.setValueAtTime(f0, t);
  if (f1 !== f0) osc.frequency.exponentialRampToValueAtTime(f1, t + dur);
  amp.gain.setValueAtTime(0.0001, t);
  amp.gain.exponentialRampToValueAtTime(gain * VOLUME, t + 0.005);
  amp.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  let out = osc;
  if (lowpass) {
    const lp = a.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = lowpass;
    out = osc.connect(lp);
  }
  out.connect(amp).connect(a.destination);
  osc.start(t);
  osc.stop(t + dur + 0.03);
}

const press = () => chirp(440, 880, 0.06, 0.18);
const release = () => chirp(990, 990, 0.035, 0.08);

// correct flag: a fast rising four-note arpeggio
export function playCorrect() {
  [523, 659, 784, 1047].forEach((f, i) =>
    chirp(f, f, i === 3 ? 0.3 : 0.08, 0.15, i * 0.08),
  );
}

// wrong flag: a firm low "bonk-bonk", an NES-style lead (two slightly detuned squares) over a bass note
export function playWrong() {
  [0, 0.16].forEach(at => {
    chirp(196, 165, 0.12, 0.09, at, "square", 0, 3200);
    chirp(196, 165, 0.12, 0.09, at, "square", 3, 3200);
    chirp(98, 98, 0.14, 0.45, at, "triangle");
  });
}

function button(target) {
  const el = target instanceof Element ? target.closest(BUTTONS) : null;
  return el && !el.disabled && !el.classList.contains("disabled") ? el : null;
}

export default () => {
  let down = null;
  document.addEventListener("pointerdown", e => {
    if (e.button !== 0) return;
    down = button(e.target);
    if (down) press();
  });
  document.addEventListener("pointerup", () => {
    if (down) release();
    down = null;
  });
  document.addEventListener("pointercancel", () => (down = null));

  // keyboard presses of a focused button click too
  document.addEventListener("keydown", e => {
    if ((e.key === "Enter" || e.key === " ") && !e.repeat && button(e.target)) press();
  });
  document.addEventListener("keyup", e => {
    if ((e.key === "Enter" || e.key === " ") && button(e.target)) release();
  });
};
