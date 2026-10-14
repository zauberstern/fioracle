/** Episode pins on the shared history tape (PIT-valid dates). One SoT for body + game. */

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
    title: "History starts",
    blurb: "The first date this history can show.",
  },
  {
    id: "gfc",
    date: "2008-09-15",
    title: "Lehman bank crisis",
    blurb: "Credit froze that week.",
  },
  {
    id: "covid",
    date: "2020-03-16",
    title: "Covid market shock",
    blurb: "A sudden cash squeeze in March 2020.",
  },
  {
    id: "tightening",
    date: "2022-01-03",
    title: "Interest rates rise",
    blurb: "Rates rose into a crowded bond and high-yield book.",
  },
  {
    id: "banks23",
    date: "2023-03-10",
    title: "Regional bank run",
    blurb: "High-yield insurance stands in for a single company's cover.",
  },
];
