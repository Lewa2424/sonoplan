/** UUID v4 string (DAT-001: все сущности получают UUID). */
export type Uuid = string & { readonly __brand: "Uuid" };

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isUuid(value: string): value is Uuid {
  return UUID_RE.test(value);
}

export function asUuid(value: string): Uuid {
  if (!isUuid(value)) {
    throw new Error(`Invalid UUID: ${value}`);
  }
  return value;
}

/** Создаёт UUID через crypto.randomUUID (браузер / Node ≥ 19). */
export function createUuid(): Uuid {
  return crypto.randomUUID() as Uuid;
}
