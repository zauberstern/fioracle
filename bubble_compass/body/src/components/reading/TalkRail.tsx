import { NARRATOR_QUESTIONS, answerQuestion, type NarratorContext, type NarratorQuestionId } from "../../narrator/narrator";

type Props = {
  open: boolean;
  onClose: () => void;
  ctx: NarratorContext;
  activeId: NarratorQuestionId | null;
  onAsk: (id: NarratorQuestionId) => void;
};

export function TalkRail({
  open,
  onClose,
  ctx,
  activeId,
  onAsk,
}: Props) {
  if (!open) return null;
  const answer = activeId ? answerQuestion(activeId, ctx) : null;

  return (
      <aside className="talk-rail" aria-label="Ask the reading">
      <div className="talk-rail-head">
        <h2>Ask the reading</h2>
        <button type="button" className="talk-rail-close" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="talk-rail-chips">
        {NARRATOR_QUESTIONS.map((q) => (
          <button
            key={q.id}
            type="button"
            className={
              activeId === q.id ? "talk-chip talk-chip-active" : "talk-chip"
            }
            onClick={() => onAsk(q.id)}
          >
            {q.label}
          </button>
        ))}
      </div>
      {answer ? (
        <div className="talk-rail-answer">
          {answer.sentences.map((s, i) => (
            <p key={i}>{s}</p>
          ))}
        </div>
      ) : (
        <p className="talk-rail-hint">
          Select a question. Each answer cites the series and the date it uses.
        </p>
      )}
    </aside>
  );
}
