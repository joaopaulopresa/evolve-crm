import { type Deal, OPEN_STAGES, type Stage, STAGES } from "./types";

export type Column = { stage: Stage; label: string; deals: Deal[]; value: number; share: number };

/** Groups deals into board columns. `share` is the column's part of the open pipeline value (0–1). */
export function buildColumns(deals: Deal[]): Column[] {
  const openValue = deals
    .filter((deal) => OPEN_STAGES.includes(deal.stage))
    .reduce((sum, deal) => sum + deal.value, 0);

  return STAGES.map(({ id, label }) => {
    const inStage = deals.filter((deal) => deal.stage === id);
    const value = inStage.reduce((sum, deal) => sum + deal.value, 0);
    const share = OPEN_STAGES.includes(id) && openValue > 0 ? value / openValue : 0;
    return { stage: id, label, deals: inStage, value, share };
  });
}
