export function PitchView() {
  return (
    <article className="reading-page pitch-view">
      <h1>Meridian</h1>
      <p className="reading-lede">
        A point-in-time reading of how high 23 public books sit on one date.
      </p>
      <div className="pitch-body">
        <p>
          You pin a date. Meridian uses only the rows published on or before
          that date. Heat runs from 0 to 100. Under 40 the marks are quiet.
          From 40 they are warming. From 70 they are stretched.
        </p>
        <p>
          Heat is the compass number. Four algorithms can add to it, and the
          sum stops at 100. Cash is left out of the ranking.
        </p>
        <p>
          DLinear, from Zeng, Chen, Zhang and Xu (2022), draws the path a book
          had been following. Heat counts how many steps the book sits above
          that path. Each step adds 12 points, and this part stops at 40.
        </p>
        <p>
          The Phillips, Shi and Yu (2015) screen asks whether that rise is
          speeding up past an ordinary line at 1.49. When the check is on, this
          part starts at 25 and adds 8 points for each unit past that line.
        </p>
        <p>
          LPPLS, the log-periodic fit, can add up to 30 points toward a date
          for a break, when that fit exists. FinBERT can add up to 15 points
          from how fast news tone is changing, when headlines exist. On this
          history both of those layers are marked unavailable, so each adds 0.
          The number on the page is the DLinear distance plus the Phillips, Shi
          and Yu screen.
        </p>
        <p>
          The matrix on the week page is one cell per book. Ask the reading
          and each answer names the book and the date it uses.
        </p>
        <p>
          Stillmoor is the same history, played as a desk. Set a weight on each
          book and stamp the sundial. A stamp scores that day when every book
          and the bench have a print. A missing print does not score.
        </p>
        <p>
          These figures describe the public marks for the date you pinned. They
          are not a forecast or a recommendation.
        </p>
      </div>
    </article>
  );
}
