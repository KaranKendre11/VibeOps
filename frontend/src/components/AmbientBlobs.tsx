import { PlexusBackground } from './PlexusBackground';

/**
 * The app-wide backdrop: a full-bleed "Plexus"-style animated network — glowing
 * cyan/violet points drifting on pure black, joined by distance-faded links — under
 * a legibility scrim so dense content stays readable. Dense code/log panels sit on
 * opaque `surface-solid`; glass panels frost the field behind them. The
 * <PlexusBackground> canvas owns its own prefers-reduced-motion behavior (it renders
 * a single static frame instead of animating).
 */
export function AmbientBlobs() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-bg">
      {/* Deep crimson nebula wash — large soft magenta/crimson glows give the whole
          app the cosmic hue of the landing, under the network field. */}
      <div
        className="absolute inset-0 z-0"
        style={{
          background:
            'radial-gradient(60% 55% at 22% 18%, rgba(143,29,74,0.60) 0%, transparent 60%),' +
            'radial-gradient(55% 50% at 82% 30%, rgba(255,77,141,0.30) 0%, transparent 62%),' +
            'radial-gradient(70% 60% at 55% 100%, rgba(110,20,58,0.60) 0%, transparent 65%)',
        }}
      />
      {/* Animated network field. Sits below the overlays (z-10/z-20). */}
      <PlexusBackground className="absolute inset-0 z-0 h-full w-full" />

      {/* Legibility scrim — darker at the top (nav) and bottom, lighter through the
          middle so the field reads clearly while text stays legible. */}
      <div
        className="absolute inset-0 z-10"
        style={{
          background:
            'linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.28) 34%, rgba(0,0,0,0.28) 66%, rgba(0,0,0,0.58) 100%)',
        }}
      />
      {/* Vignette keeps the frame dark at the edges. */}
      <div
        className="absolute inset-0 z-20"
        style={{
          background: 'radial-gradient(ellipse 120% 90% at 50% 40%, transparent 46%, rgba(0, 0, 0, 0.55) 100%)',
        }}
      />
    </div>
  );
}
