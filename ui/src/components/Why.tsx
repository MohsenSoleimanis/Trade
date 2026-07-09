// The teaching layer, as a component. Every metric the app shows can
// carry one of these: what the number is, why it matters, which lesson
// it comes from. The product contract: never a number without a why.

export function Why(props: { lesson: string; children: React.ReactNode }) {
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
