export const defaults: Readonly<{
  speed: number;
  interval: number;
  fontSize: number;
  density: number;
  lineHeight: number;
  decay: number;
  opacity: number;
  radius: number;
  glowDecay: number;
  glowBrightness: number;
  color: string;
  glowColor: string;
  background: string;
  characters: string;
  mask: boolean;
  pointer: boolean;
}>;

export function normalizeSettings(options?: Partial<typeof defaults>): typeof defaults;
export function createRain(canvas: HTMLCanvasElement, source?: Partial<typeof defaults>): {
  update(key: string): void;
  rebuild(): void;
  pause(): boolean;
  destroy(): void;
};
