// Mentor mode — audit Finding 5, fixed: the teaching layer is now opt-in.
// Off by default; the tool stands alone. One tiny pub/sub, persisted.

const KEY = "dewaag-mentor";

export function mentorOn(): boolean {
  return localStorage.getItem(KEY) === "1";
}

export function toggleMentor(): boolean {
  const next = !mentorOn();
  localStorage.setItem(KEY, next ? "1" : "0");
  window.dispatchEvent(new CustomEvent("mentor-changed"));
  return next;
}

export function onMentorChange(fn: () => void): () => void {
  window.addEventListener("mentor-changed", fn);
  return () => window.removeEventListener("mentor-changed", fn);
}
