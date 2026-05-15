export type ReminderScheduleRule = {
  offsetDays: number;
  enabled: boolean;
};

export const DEFAULT_REMINDER_RULES: ReminderScheduleRule[] = [
  { offsetDays: -3, enabled: true },
  { offsetDays: 0, enabled: true },
  { offsetDays: 3, enabled: true },
  { offsetDays: 7, enabled: true },
];

export function loadReminderScheduleRules(source: unknown): ReminderScheduleRule[] {
  const rawRules = Array.isArray(source) ? source : DEFAULT_REMINDER_RULES;
  const rules = rawRules.map(normalizeRule).filter(isReminderScheduleRule);

  return rules.length > 0 ? sortRules(rules) : sortRules(DEFAULT_REMINDER_RULES);
}

export function enabledReminderRules(source: unknown): ReminderScheduleRule[] {
  return loadReminderScheduleRules(source).filter((rule) => rule.enabled);
}

function normalizeRule(rule: unknown): Partial<ReminderScheduleRule> {
  if (!rule || typeof rule !== "object") {
    return {};
  }

  const raw = rule as {
    offsetDays?: unknown;
    offset_days?: unknown;
    enabled?: unknown;
  };

  return {
    offsetDays: numberValue(raw.offsetDays ?? raw.offset_days),
    enabled: raw.enabled !== false,
  };
}

function isReminderScheduleRule(rule: Partial<ReminderScheduleRule>): rule is ReminderScheduleRule {
  return Number.isInteger(rule.offsetDays) && typeof rule.enabled === "boolean";
}

function numberValue(value: unknown): number | undefined {
  if (typeof value === "number") {
    return value;
  }

  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isInteger(parsed) ? parsed : undefined;
  }

  return undefined;
}

function sortRules(rules: ReminderScheduleRule[]): ReminderScheduleRule[] {
  return [...rules].sort((a, b) => a.offsetDays - b.offsetDays);
}
