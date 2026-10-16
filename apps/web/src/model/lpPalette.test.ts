import { describe, expect, it } from "vitest";
import {
  computeLpScale,
  formatLpScaleLegend,
  lpToRgba,
} from "./lpPalette";

describe("lpPalette auto scale", () => {
  it("computes min/max from finite cells only", () => {
    const scale = computeLpScale([null, 58.1, 95.5, null, 70]);
    expect(scale).toEqual({ minDb: 58.1, maxDb: 95.5 });
  });

  it("returns null when no energy cells", () => {
    expect(computeLpScale([null, null])).toBeNull();
  });

  it("maps low to teal-ish and high to red under auto scale", () => {
    const scale = { minDb: 60, maxDb: 90 };
    const low = lpToRgba(60, scale);
    const high = lpToRgba(90, scale);
    expect(low[3]).toBeGreaterThan(0);
    expect(high[0]).toBeGreaterThan(low[0]!);
    expect(high[3]).toBeGreaterThan(0);
  });

  it("formats legend with dB range", () => {
    expect(formatLpScaleLegend({ minDb: 58.13, maxDb: 95.57 })).toContain(
      "58.1…95.6 дБ",
    );
  });
});
