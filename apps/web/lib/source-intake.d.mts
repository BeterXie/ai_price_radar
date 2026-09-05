export type IntakeSourceType = "auto" | "ldxp" | "dujiao_next" | "merchant_json" | "woocommerce" | "16688" | "schema_org" | "other";

export const SOURCE_INTAKE_OPTIONS: { id: IntakeSourceType; label: string; disabled?: boolean }[];
export const SOURCE_INTAKE_COPY: Record<IntakeSourceType, { fieldLabel: string; placeholder: string; hint: string }>;
export function isValidPublicSourceUrl(value: string): boolean;
