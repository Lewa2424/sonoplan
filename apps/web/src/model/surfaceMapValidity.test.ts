import { describe, expect, it } from "vitest";
import { surfaceGridRejectReason, surfaceMapFromManifest } from "./surfaceMapValidity";

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

describe("surfaceMapFromManifest", () => {
  const full = grid(4, 3, () => true);
  const manifest = {
    mapAvailable: true,
    grid: {
      originX: -0.01,
      originY: -0.01,
      cellSizeM: 0.15,
      nx: full.nx,
      ny: full.ny,
      zM: 1.85,
      lpDb: full.lpDb,
      laDb: full.lpDb.map((v) => (v === null ? null : v - 3)),
    },
    exportMeta: { mode: "export_box", originX: 10, originY: 5 },
  };

  it("returns null when the adapter did not publish a map", () => {
    expect(surfaceMapFromManifest({ mapAvailable: false })).toBeNull();
    expect(surfaceMapFromManifest(null)).toBeNull();
  });

  it("moves the SPPS grid into project coordinates and uses dBA", () => {
    const r = surfaceMapFromManifest(manifest);
    expect(r?.ok).toBe(true);
    if (!r?.ok) return;
    expect(r.grid.originX).toBeCloseTo(9.99, 9);
    expect(r.grid.originY).toBeCloseTo(4.99, 9);
    expect(r.grid.cellSizeYM).toBe(0.15);
    expect(r.grid.zM).toBe(1.85);
    expect(r.grid.laDb[0]).toBe(77);
  });

  it("hides jobs computed before A-weighting instead of showing dB as dBA", () => {
    const { laDb: _drop, ...legacyGrid } = manifest.grid;
    expect(surfaceMapFromManifest({ ...manifest, grid: legacyGrid })).toEqual({
      ok: false,
      reason: "notAWeighted",
    });
  });

  it("hides a grid without a known project frame (fixture / old export)", () => {
    expect(surfaceMapFromManifest({ ...manifest, exportMeta: { mode: "export_box" } })).toEqual(
      { ok: false, reason: "noFrame" },
    );
    expect(surfaceMapFromManifest({ ...manifest, exportMeta: undefined })).toEqual({
      ok: false,
      reason: "noFrame",
    });
  });

  it("applies the plausibility gate first", () => {
    const patch = grid(67, 41, (i, j) => i < 45 && j < 28);
    expect(
      surfaceMapFromManifest({
        ...manifest,
        grid: { ...manifest.grid, ...patch, laDb: patch.lpDb },
      }),
    ).toEqual({ ok: false, reason: "partialCoverage" });
  });
});
