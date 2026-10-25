export type IntakeSourceType = "ldxp" | "16688" | "independent" | "relay";

export const SOURCE_INTAKE_OPTIONS: { id: IntakeSourceType; label: string }[];
export const SOURCE_INTAKE_COPY: Record<IntakeSourceType, { fieldLabel: string; placeholder: string; hint: string }>;
export function isValidPublicSourceUrl(value: string): boolean;
