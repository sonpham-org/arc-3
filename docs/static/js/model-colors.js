// Model colours on the RL, Trace review and Tree pages (Son 2-Oct: blue theme instead of orange). "Before training"
// is a muted slate blue and each later round a stronger blue, darker on the light theme and lighter on the dark one,
// so every round reads on its background and later rounds stand out.
const STEPS = {
  light: ["#7d93b6", "#2563eb", "#1e3a8a", "#172554", "#0b1530"],
  dark: ["#7f98c4", "#60a5fa", "#bfdbfe", "#e0f2fe", "#f8fbff"],
};

export const isLight = () => document.documentElement.getAttribute("data-theme") === "light";

// i: the model's place in round order (0 = before training, 1 = after round 0, ...)
export function modelColor(i) {
  const s = STEPS[isLight() ? "light" : "dark"];
  return s[Math.max(0, Math.min(i, s.length - 1))];
}
