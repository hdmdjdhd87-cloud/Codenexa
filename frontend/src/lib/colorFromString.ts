/**
 * Детерминированный акцентный цвет по строке (module_key/category/name) —
 * используется и в Avatar, и в ModuleCard, чтобы одна и та же сущность
 * всегда получала один и тот же цвет, без обращения к серверу за палитрой.
 */
const PALETTE = [
  { bg: "#6C63FF", tint: "#6C63FF1F" },
  { bg: "#3FA7D6", tint: "#3FA7D61F" },
  { bg: "#4C7A3D", tint: "#4C7A3D1F" },
  { bg: "#E8A93B", tint: "#E8A93B1F" },
  { bg: "#B5544A", tint: "#B5544A1F" },
  { bg: "#C060E0", tint: "#C060E01F" },
];

export function colorFromString(input: string): { bg: string; tint: string } {
  let hash = 0;
  for (let i = 0; i < input.length; i++) hash = input.charCodeAt(i) + ((hash << 5) - hash);
  return PALETTE[Math.abs(hash) % PALETTE.length];
}
