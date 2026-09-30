/** Episode pins on the shared history tape (PIT-valid dates). */
export type EpisodePin = {
  id: string;
  date: string;
  title: string;
  blurb: string;
};

export const EPISODES: EpisodePin[] = [
  {
    id: "dotcom",
    date: "2008-01-02",
    title: "Tape open (post-dot-com)",
    blurb: "History parquet starts 2008; pin jumps to first available as-of.",
  },
  {
    id: "gfc",
    date: "2008-09-15",
    title: "Lehman weekend",
    blurb: "Credit freeze. Stretch and crash-window layers on the tape.",
  },
  {
    id: "covid",
    date: "2020-03-16",
    title: "COVID crash",
    blurb: "Liquidity shock. Same as-of contract as the desk game.",
  },
  {
    id: "tightening",
    date: "2022-01-03",
    title: "2022 tightening",
    blurb: "Rate shock into crowded duration and HY.",
  },
  {
    id: "banks23",
    date: "2023-03-10",
    title: "SVB / Credit Suisse",
    blurb: "Bank run week. Index HY/CDX stand in when issuer CDS is absent.",
  },
];
