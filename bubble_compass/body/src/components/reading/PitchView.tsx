import katex from "katex";
import "katex/dist/katex.min.css";
import { PITCH_BLOCKS } from "../../narrator/pitchCopy";

function Equation({ tex }: { tex: string }) {
  const html = katex.renderToString(tex, {
    displayMode: true,
    throwOnError: false,
  });
  return <div className="pitch-eq" dangerouslySetInnerHTML={{ __html: html }} />;
}

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
            return <Equation key={block.text} tex={block.text} />;
          }
          return <p key={block.text}>{block.text}</p>;
        })}
      </div>
    </article>
  );
}
