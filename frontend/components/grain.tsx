/**
 * Paper grain laid over the whole page. Without it the flat fills read as
 * vector art; with it they read as printed stock.
 */
export function Grain() {
  return (
    <svg
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-[9999] h-full w-full opacity-[0.22] mix-blend-multiply dark:opacity-[0.16] dark:mix-blend-overlay"
    >
      <filter id="mv-grain">
        <feTurbulence type="fractalNoise" baseFrequency="0.88" numOctaves="3" stitchTiles="stitch" />
      </filter>
      <rect width="100%" height="100%" filter="url(#mv-grain)" />
    </svg>
  );
}
