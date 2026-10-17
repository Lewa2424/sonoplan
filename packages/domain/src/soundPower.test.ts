import { describe, expect, it } from "vitest";
import { flatLwSpectrumForLwA, totalLwA } from "./soundPower.js";

const OCTAVES = [63, 125, 250, 500, 1000, 2000, 4000, 8000];

describe("sound power LwA", () => {
  it("flat octave spectrum sits 7.0 dB below its total LwA", () => {
    const spectrum = flatLwSpectrumForLwA(95, OCTAVES);
    expect(spectrum).toHaveLength(8);
    for (const band of spectrum) expect(band.level.value!).toBeCloseTo(88.0, 1);
    expect(totalLwA(spectrum)).toBeCloseTo(95, 9);
  });

  it("applies A-weighting once per band, summing by energy", () => {
    // 1 кГц: A = 0; 125 Гц: A = −16.1.
    const lwa = totalLwA([
      { bandHz: 125, level: { value: 90, unit: "dB" } },
      { bandHz: 1000, level: { value: 90, unit: "dB" } },
    ]);
    expect(lwa).toBeCloseTo(10 * Math.log10(10 ** 7.39 + 10 ** 9), 9);
  });

  it("ignores unknown bands and returns null without any", () => {
    expect(totalLwA([{ bandHz: 1000, level: { value: null, unit: "dB" } }])).toBeNull();
    expect(
      totalLwA([
        { bandHz: 1000, level: { value: 80, unit: "dB" } },
        { bandHz: 500, level: { value: null, unit: "dB" } },
      ]),
    ).toBeCloseTo(80, 9);
  });

  it("refuses non-nominal bands instead of guessing the correction", () => {
    expect(() => flatLwSpectrumForLwA(90, [1100])).toThrow(RangeError);
  });
});
