import { useEffect, useState } from "react";
import { mentorOn, onMentorChange } from "../mentor";

// The teaching layer — rendered ONLY in mentor mode (off by default).
// The tool must stand alone; the teacher appears when invited.

export function Why(props: { lesson: string; children: React.ReactNode }) {
  const [on, setOn] = useState(mentorOn());
  useEffect(() => onMentorChange(() => setOn(mentorOn())), []);
  if (!on) return null;
  return (
    <details className="why">
      <summary>why this matters</summary>
      <div className="body">
        {props.children}{" "}
        <span className="lesson">→ {props.lesson}</span>
      </div>
    </details>
  );
}
