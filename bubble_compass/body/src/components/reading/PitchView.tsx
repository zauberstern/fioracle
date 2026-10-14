import { PITCH_BLOCKS } from "../../narrator/pitchCopy";

export function PitchView() {
  return (
    <article className="reading-page pitch-view">
      <h1>Meridian</h1>
      <div className="pitch-body">
        {PITCH_BLOCKS.map((block) => {
          if (block.kind === "h") {
            return <h2 key={block.text}>{block.text}</h2>;
          }
          if (block.kind === "eq") {
            return (
              <p key={block.text} className="pitch-eq">
                {block.text}
              </p>
            );
          }
          return <p key={block.text}>{block.text}</p>;
        })}
      </div>
    </article>
  );
}
