import {
  NOISE_SCALE_UNIT,
  noiseScaleCssGradient,
  noiseScaleSpanDb,
  noiseScaleTicksDb,
} from "../model/lpPalette";
import { ru } from "../i18n/ru";

const GRADIENT = noiseScaleCssGradient();
const SPAN = noiseScaleSpanDb();
const TICKS = noiseScaleTicksDb();

/** Фиксированная шкала карты (те же цвета, что и ячейки на плане). */
export function NoiseScaleLegend({ caption }: { caption: string }) {
  return (
    <figure className="noise-legend" aria-label={`${caption}, ${NOISE_SCALE_UNIT}`}>
      <figcaption className="noise-legend__caption">
        {caption}, {NOISE_SCALE_UNIT} · {ru.calculations.scaleSource}
      </figcaption>
      <div className="noise-legend__bar" style={{ background: GRADIENT }} />
      <div className="noise-legend__ticks" aria-hidden="true">
        {TICKS.map((db) => (
          <span
            key={db}
            className="noise-legend__tick"
            style={{ left: `${((db - SPAN.loDb) / (SPAN.hiDb - SPAN.loDb)) * 100}%` }}
          >
            {db}
          </span>
        ))}
      </div>
    </figure>
  );
}
