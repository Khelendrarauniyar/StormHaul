import type { RiskLevelName } from "../types";

export interface RiskMeta {
  label: string;
  color: string;
  rank: number;
  icon: string;
}

export const RISK_META: Record<RiskLevelName, RiskMeta> = {
  low: { label: "Low", color: "#1b8a4b", rank: 0, icon: "OK" },
  moderate: { label: "Moderate", color: "#c98a00", rank: 1, icon: "!" },
  high: { label: "High", color: "#e0641a", rank: 2, icon: "!!" },
  severe: { label: "Severe", color: "#cc2b2b", rank: 3, icon: "!!!" },
  no_travel: { label: "No Travel", color: "#231f2e", rank: 4, icon: "STOP" },
};

export const RISK_ORDER: RiskLevelName[] = [
  "low",
  "moderate",
  "high",
  "severe",
  "no_travel",
];

export function riskColor(level?: RiskLevelName | null): string {
  if (!level) {
    return "#8a8f98";
  }
  return RISK_META[level].color;
}

export function riskLabel(level?: RiskLevelName | null): string {
  if (!level) {
    return "Unavailable";
  }
  return RISK_META[level].label;
}
