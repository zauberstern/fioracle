/** Display names for every book on the published tape. */

export type Book = {
  id: string;
  name: string;
  short: string;
  plain: string;
  mark: string;
  group: string;
  hint: string;
  cash?: boolean;
};

export const BOOKS: readonly Book[] = [
  {
    id: "SP500_TOTAL_RETURN",
    name: "Stocks",
    short: "US stocks",
    plain: "US stocks",
    mark: "🇺🇸",
    group: "US stocks",
    hint: "S&P 500 total return. Large companies listed in the United States.",
  },
  {
    id: "BBG_US_HIGH_YIELD_TOTAL_RETURN",
    name: "High yield",
    short: "US junk",
    plain: "US junk bonds",
    mark: "🇺🇸",
    group: "US credit",
    hint: "Bloomberg US High Yield total return. Dollar bonds of US companies rated below investment grade.",
  },
  {
    id: "BBG_US_CORPORATE_TOTAL_RETURN",
    name: "Corporates",
    short: "US IG",
    plain: "US company bonds",
    mark: "🇺🇸",
    group: "US credit",
    hint: "Bloomberg US Corporate total return. Dollar bonds of US companies rated investment grade.",
  },
  {
    id: "BBG_US_TREASURY_TOTAL_RETURN",
    name: "Treasuries",
    short: "US Tsies",
    plain: "US Treasuries",
    mark: "🇺🇸",
    group: "US rates",
    hint: "Bloomberg US Treasury total return. US government notes and bonds across maturities.",
  },
  {
    id: "GOLD_TOTAL_RETURN",
    name: "Gold",
    short: "Gold",
    plain: "Gold",
    mark: "🥇",
    group: "Commodities",
    hint: "Gold total return. The metal, not a mining stock.",
  },
  {
    id: "US_CASH_RETURN",
    name: "Cash",
    short: "T-bills",
    plain: "US T-bills",
    mark: "💵",
    group: "Cash",
    hint: "US Treasury bills. Short US government paper. Heat stays at 0.",
    cash: true,
  },
  {
    id: "CDX_HY_5Y_TOTAL_RETURN",
    name: "High-yield insurance",
    short: "Junk CDS",
    plain: "Junk default swaps",
    mark: "🛡️",
    group: "US credit",
    hint: "CDX High Yield 5-year total return. A contract that pays if a basket of US junk borrowers defaults.",
  },
  {
    id: "CDX_IG_5Y_TOTAL_RETURN",
    name: "Investment-grade insurance",
    short: "IG CDS",
    plain: "IG default swaps",
    mark: "🛡️",
    group: "US credit",
    hint: "CDX Investment Grade 5-year total return. A contract that pays if a basket of US investment-grade borrowers defaults.",
  },
  {
    id: "BBG_GLOBAL_AGG_TOTAL_RETURN",
    name: "Global bonds",
    short: "World",
    plain: "World bonds",
    mark: "🌍",
    group: "World bonds",
    hint: "Bloomberg Global Aggregate total return. Government and company bonds from many countries.",
  },
  {
    id: "BBG_EURO_AGG_CHF_HEDGED_TOTAL_RETURN",
    name: "Europe bonds",
    short: "Europe",
    plain: "Europe bonds",
    mark: "🇪🇺",
    group: "World bonds",
    hint: "Bloomberg Euro Aggregate, hedged into Swiss francs. European bonds with the franc move taken out.",
  },
  {
    id: "US_BOND_AGG_TOTAL_RETURN",
    name: "US aggregate bonds",
    short: "US agg",
    plain: "US bond market",
    mark: "🇺🇸",
    group: "US rates",
    hint: "US Aggregate Bond total return. The broad US taxable bond market: Treasuries, mortgages, and company bonds.",
  },
  {
    id: "US_TIPS_0_5_TOTAL_RETURN",
    name: "US inflation-linked",
    short: "US TIPS",
    plain: "US TIPS",
    mark: "🇺🇸",
    group: "Inflation",
    hint: "US TIPS, 0 to 5 years. Short US government bonds whose principal tracks US consumer prices.",
  },
  {
    id: "GLOBAL_ILB_0_5_TOTAL_RETURN",
    name: "Global inflation-linked",
    short: "World IL",
    plain: "World inflation bonds",
    mark: "🌍",
    group: "Inflation",
    hint: "Global inflation-linked bonds, 0 to 5 years. Short government linkers from several countries.",
  },
  {
    id: "ISHARES_20Y_TREASURY_TOTAL_RETURN",
    name: "Long Treasuries",
    short: "Long UST",
    plain: "Long US Treasuries",
    mark: "🇺🇸",
    group: "US rates",
    hint: "iShares 20+ Year Treasury (TLT). US government bonds with 20 years or more left.",
  },
  {
    id: "ISHARES_7_10Y_TREASURY_TOTAL_RETURN",
    name: "Intermediate Treasuries",
    short: "Mid UST",
    plain: "Medium US Treasuries",
    mark: "🇺🇸",
    group: "US rates",
    hint: "iShares 7-10 Year Treasury (IEF). US government notes around 7 to 10 years.",
  },
  {
    id: "ISHARES_1_3Y_TREASURY_TOTAL_RETURN",
    name: "Short Treasuries",
    short: "Short UST",
    plain: "Short US Treasuries",
    mark: "🇺🇸",
    group: "US rates",
    hint: "iShares 1-3 Year Treasury (SHY). US government notes around 1 to 3 years.",
  },
  {
    id: "ISHARES_SWISS_GOV_7_15_TOTAL_RETURN",
    name: "Swiss government bonds",
    short: "Swiss",
    plain: "Swiss government",
    mark: "🇨🇭",
    group: "Swiss",
    hint: "iShares Swiss government bonds, 7 to 15 years (CSBGC0.SW). Confederation notes in francs.",
  },
  {
    id: "WTI_TOTAL_RETURN",
    name: "Oil",
    short: "Oil",
    plain: "Oil",
    mark: "🛢️",
    group: "Commodities",
    hint: "WTI crude oil total return. West Texas Intermediate, the US crude benchmark.",
  },
  {
    id: "VRP_HARVEST_TOTAL_RETURN",
    name: "Volatility premium",
    short: "Vol",
    plain: "Vol harvest",
    mark: "📉",
    group: "Other",
    hint: "Volatility risk premium harvest. A book that sells US equity volatility and keeps the premium when markets stay calm.",
  },
  {
    id: "CHF_TOTAL_RETURN",
    name: "Swiss franc",
    short: "Franc",
    plain: "Swiss franc",
    mark: "🇨🇭",
    group: "Swiss",
    hint: "Swiss franc total return. Cash in francs, rolled in the money market.",
  },
  {
    id: "US_AAA_CORP_BOND_TOTAL_RETURN",
    name: "AAA corporates",
    short: "AAA",
    plain: "AAA company bonds",
    mark: "🇺🇸",
    group: "US credit",
    hint: "US AAA corporate total return. Dollar bonds of the highest-rated US companies.",
  },
  {
    id: "US_BAA_CORP_BOND_TOTAL_RETURN",
    name: "BAA corporates",
    short: "Baa",
    plain: "Baa company bonds",
    mark: "🇺🇸",
    group: "US credit",
    hint: "US Baa corporate total return. Dollar bonds of US companies at the bottom of investment grade (Moody's Baa).",
  },
  {
    id: "IBOXX_UK_IL_GILT_TOTAL_RETURN",
    name: "UK inflation-linked",
    short: "UK IL",
    plain: "UK inflation gilts",
    mark: "🇬🇧",
    group: "Inflation",
    hint: "iBoxx UK inflation-linked gilts. UK government bonds whose payments track UK inflation.",
  },
];

export function bookName(id: string): string {
  return BOOKS.find((b) => b.id === id)?.name ?? "This book";
}

export function bookShort(id: string): string {
  return BOOKS.find((b) => b.id === id)?.short ?? bookName(id);
}

export function bookHint(id: string): string {
  return BOOKS.find((b) => b.id === id)?.hint ?? "";
}
