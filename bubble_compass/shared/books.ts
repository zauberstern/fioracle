/** Display names for every book on the published tape. */

export type Book = {
  id: string;
  name: string;
  cash?: boolean;
};

export const BOOKS: readonly Book[] = [
  { id: "SP500_TOTAL_RETURN", name: "Stocks" },
  { id: "BBG_US_HIGH_YIELD_TOTAL_RETURN", name: "High yield" },
  { id: "BBG_US_CORPORATE_TOTAL_RETURN", name: "Corporates" },
  { id: "BBG_US_TREASURY_TOTAL_RETURN", name: "Treasuries" },
  { id: "GOLD_TOTAL_RETURN", name: "Gold" },
  { id: "US_CASH_RETURN", name: "Cash", cash: true },
  { id: "CDX_HY_5Y_TOTAL_RETURN", name: "High-yield insurance" },
  { id: "CDX_IG_5Y_TOTAL_RETURN", name: "Investment-grade insurance" },
  { id: "BBG_GLOBAL_AGG_TOTAL_RETURN", name: "Global bonds" },
  { id: "BBG_EURO_AGG_CHF_HEDGED_TOTAL_RETURN", name: "Europe bonds" },
  { id: "US_BOND_AGG_TOTAL_RETURN", name: "US aggregate bonds" },
  { id: "US_TIPS_0_5_TOTAL_RETURN", name: "US inflation-linked" },
  { id: "GLOBAL_ILB_0_5_TOTAL_RETURN", name: "Global inflation-linked" },
  { id: "ISHARES_20Y_TREASURY_TOTAL_RETURN", name: "Long Treasuries" },
  { id: "ISHARES_7_10Y_TREASURY_TOTAL_RETURN", name: "Intermediate Treasuries" },
  { id: "ISHARES_1_3Y_TREASURY_TOTAL_RETURN", name: "Short Treasuries" },
  { id: "ISHARES_SWISS_GOV_7_15_TOTAL_RETURN", name: "Swiss government bonds" },
  { id: "WTI_TOTAL_RETURN", name: "Oil" },
  { id: "VRP_HARVEST_TOTAL_RETURN", name: "Volatility premium" },
  { id: "CHF_TOTAL_RETURN", name: "Swiss franc" },
  { id: "US_AAA_CORP_BOND_TOTAL_RETURN", name: "AAA corporates" },
  { id: "US_BAA_CORP_BOND_TOTAL_RETURN", name: "BAA corporates" },
  { id: "IBOXX_UK_IL_GILT_TOTAL_RETURN", name: "UK inflation-linked" },
];

export function bookName(id: string): string {
  return BOOKS.find((b) => b.id === id)?.name ?? "This book";
}
