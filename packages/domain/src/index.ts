export {
  PROJECT_SCHEMA_VERSION,
  LEGACY_PROJECT_SCHEMA_VERSIONS,
  type ProjectSchemaVersion,
  type LegacyProjectSchemaVersion,
  type UtcIsoDateTime,
  type Project,
  type Revision,
  type FloorVertex,
  type Room,
  type RoomSurfaceKind,
  type RoomSurfaceMaterials,
  type MaterialVersion,
  type AbsorptionBand,
  type SolidObstacle,
  type OctaveBandLevel,
  type Source,
  type WorkplaceKind,
  type Workplace,
  type ModelSnapshot,
  type ProjectDraft,
  type ValidationSeverity,
  type ValidationIssue,
} from "./types.js";

export {
  type Uuid,
  isUuid,
  asUuid,
  createUuid,
} from "./uuid.js";

export {
  type LengthUnit,
  type LevelUnit,
  type PowerLevelUnit,
  type PressureLevelUnit,
  type Quantity,
  finiteOrNull,
  unknownQuantity,
} from "./units.js";

export {
  type ProjectPoint3,
  type ThreePoint3,
  projectToThree,
  threeToProject,
} from "./coordinates.js";

export {
  type ContourErrorCode,
  type ContourError,
  stripClosingDuplicate,
  isContourExplicitlyClosed,
  findSelfIntersections,
  validateFloorContour,
  pointInPolygon,
} from "./geometry.js";

export {
  sortKeysDeep,
  canonicalJson,
  snapshotHashPayload,
  computeSnapshotHash,
  serializeModelSnapshot,
  parseModelSnapshot,
} from "./snapshot.js";

export {
  isLwUnit,
  isLpUnit,
  validateModel,
  validationOk,
} from "./validate.js";

export { sha256Hex } from "./sha256.js";

export {
  DIFFUSE_MIN_DISTANCE_M,
  type DiffuseEstimateUnavailableReason,
  type DiffuseFieldSource,
  type DiffuseFieldInput,
  type DiffuseFieldInputResult,
  type DiffuseFieldGrid,
  buildDiffuseFieldInput,
  estimateLpAt,
  estimateLpGrid,
} from "./diffuseFieldEstimate.js";

export { type LevelWeighting, aWeightingDb } from "./aWeighting.js";

export { totalLwA, flatLwSpectrumForLwA } from "./soundPower.js";

export {
  ROOM_SURFACE_KINDS,
  polygonAreaAndPerimeter,
  roomSurfaceAreasM2,
  roomSurfaceMaterial,
} from "./roomSurfaces.js";

export {
  UnsupportedSchemaVersionError,
  migrateModelSnapshot,
} from "./schemaMigration.js";

export { workplaceReceiverZ, planCutHeightM } from "./planCut.js";
