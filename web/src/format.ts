const moneyFormat = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const dayFormat = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" });

const shortDayFormat = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" });

export const money = (value: number) => moneyFormat.format(value);

/** Formats an ISO date or timestamp as "Oct 5, 2026"; date-only values are not shifted by timezone. */
export function day(value: string | null): string {
  if (!value) return "";
  const date = value.length === 10 ? new Date(`${value}T12:00:00`) : new Date(value);
  return dayFormat.format(date);
}

export const initials = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join("");

export const fullName = (person: { first_name: string; last_name: string }) =>
  `${person.first_name} ${person.last_name}`;

/** "Oct 5" for a date-only value; used where space is tight. */
export const shortDay = (value: string) => shortDayFormat.format(new Date(`${value}T12:00:00`));
