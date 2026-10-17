import { describe, expect, it } from "vitest";
import {
  NOISE_CLASSES,
  lpToRgba,
  noiseRgb,
  noiseScaleCssGradient,
  noiseScaleSpanDb,
  noiseScaleTicksDb,
} from "./lpPalette";

describe("fixed DIN 45682 noise scale (dBA)", () => {
  it("has 11 classes of 5 dB from ≤60 to >105", () => {
    expect(NOISE_CLASSES).toHaveLength(11);
    expect(NOISE_CLASSES[0]).toMatchObject({ lowerDb: null, upperDb: 60 });
    expect(NOISE_CLASSES[5]).toMatchObject({ lowerDb: 80, upperDb: 85 });
    expect(NOISE_CLASSES[10]).toMatchObject({ lowerDb: 105, upperDb: null });
    expect(noiseScaleTicksDb()).toEqual([60, 65, 70, 75, 80, 85, 90, 95, 100, 105]);
  });

  it("is absolute: the same level gets the same colour on any map", () => {
    // Class centre → exact class colour, independent of other cells.
    expect(noiseRgb(82.5)).toEqual([243, 198, 131]);
    expect(noiseRgb(97.5)).toEqual([161, 26, 77]);
  });

  it("blends smoothly between neighbouring classes", () => {
    const a = noiseRgb(82.5);
    const mid = noiseRgb(85);
    const b = noiseRgb(87.5);
    for (let k = 0; k < 3; k++) {
      expect(mid[k]).toBe(Math.round((a[k]! + b[k]!) / 2));
    }
  });

  it("clamps beyond the open end classes", () => {
    expect(noiseRgb(20)).toEqual([130, 166, 173]);
    expect(noiseRgb(140)).toEqual([67, 10, 74]);
  });

  it("keeps cells without energy transparent (not silence)", () => {
    expect(lpToRgba(null)[3]).toBe(0);
    expect(lpToRgba(Number.NaN)[3]).toBe(0);
    expect(lpToRgba(90)[3]).toBeGreaterThan(0);
  });

  it("legend gradient spans the same range as the map", () => {
    expect(noiseScaleSpanDb()).toEqual({ loDb: 55, hiDb: 110 });
    const css = noiseScaleCssGradient();
    expect(css.startsWith("linear-gradient(to right, rgb(130, 166, 173) 4.55%")).toBe(true);
    expect(css.endsWith("rgb(67, 10, 74) 95.45%)")).toBe(true);
  });
});
