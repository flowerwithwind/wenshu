/**
 * Fluid document root type scale (viewport-width driven).
 * Anchors: 14px @ 375px viewport → 18px @ 1440px (linear between).
 * CSS must mirror rootFontSizeCssClamp() on `html { font-size: ... }`.
 */

export const FLUID_ROOT_SCALE = Object.freeze({
  minWidth: 375,
  maxWidth: 1440,
  minFont: 14,
  maxFont: 18,
  /** Design rem base (px) used when converting design tokens to rem */
  remBase: 16,
});

/**
 * @param {number} viewportWidth
 * @param {Partial<typeof FLUID_ROOT_SCALE>} [opts]
 * @returns {number} root font-size in CSS px
 */
export function rootFontSizePx(viewportWidth, opts = {}) {
  const { minWidth, maxWidth, minFont, maxFont } = { ...FLUID_ROOT_SCALE, ...opts };
  const w = Number(viewportWidth);
  if (!Number.isFinite(w)) return minFont;
  if (w <= minWidth) return minFont;
  if (w >= maxWidth) return maxFont;
  const t = (w - minWidth) / (maxWidth - minWidth);
  return minFont + t * (maxFont - minFont);
}

/**
 * CSS clamp() expression matching rootFontSizePx for any viewport width
 * in [minWidth, maxWidth] (and clamped outside).
 * @param {Partial<typeof FLUID_ROOT_SCALE>} [opts]
 * @returns {string}
 */
export function rootFontSizeCssClamp(opts = {}) {
  const { minWidth, maxWidth, minFont, maxFont } = { ...FLUID_ROOT_SCALE, ...opts };
  const slope = (maxFont - minFont) / (maxWidth - minWidth);
  const vwCoef = slope * 100;
  const intercept = minFont - slope * minWidth;
  return `clamp(${minFont}px, calc(${intercept.toFixed(4)}px + ${vwCoef.toFixed(4)}vw), ${maxFont}px)`;
}

/** px design value → rem string at remBase (default 16). */
export function pxToRem(px, remBase = FLUID_ROOT_SCALE.remBase) {
  return `${Number(px) / remBase}rem`;
}
