import { describe, expect, it } from "vitest";
import { surfaceGridRejectReason } from "./surfaceMapValidity";

function grid(nx: number, ny: number, filled: (i: number, j: number) => boolean) {
  const lpDb: (number | null)[] = [];
  for (let j = 0; j < ny; j += 1) {
    for (let i = 0; i < nx; i += 1) lpDb.push(filled(i, j) ? 80 : null);
  }
  return { nx, ny, lpDb };
}

describe("surfaceGridRejectReason", () => {
  it("accepts a fully covered coupe", () => {
    expect(surfaceGridRejectReason(grid(67, 41, () => true))).toBeNull();
  });

  it("rejects the corner-only 2/3 patch seen from SPPS (job 6aed4c64)", () => {
    // Filled i<45, j<28 of 67×41: 46% fill passes the sparse gate, span does not.
    const g = grid(67, 41, (i, j) => i < 45 && j < 28);
    expect(surfaceGridRejectReason(g)).toBe("partialCoverage");
  });

  it("rejects sparse blotches before checking span", () => {
    const g = grid(10, 10, (i, j) => i === j);
    expect(surfaceGridRejectReason(g)).toBe("sparse");
  });

  it("accepts scattered holes when energy still reaches every edge", () => {
    const g = grid(20, 20, (i, j) => (i + j) % 3 !== 0);
    expect(surfaceGridRejectReason(g)).toBeNull();
  });

  it("rejects inconsistent dimensions", () => {
    expect(surfaceGridRejectReason({ nx: 3, ny: 3, lpDb: [80, 80] })).toBe(
      "dimensions",
    );
    expect(surfaceGridRejectReason({ nx: 0, ny: 3, lpDb: [] })).toBe("dimensions");
  });
});
