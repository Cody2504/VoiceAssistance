/**
 * Sidebar icons reproduced 1:1 from the TwelveLabs playground markup.
 * Each item exposes a default (outline) and hover (filled) variant; the
 * SidebarItem component picks the correct one for current state.
 */

interface IconProps {
  size?: number;
  className?: string;
}

const BASE = "fill-current";

// ── Overview (house) ────────────────────────────────────────────────────────
export function OverviewDefault({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" fillRule="evenodd" d="M3.5 13h2.125V9.6c0-.7.567-1.267 1.267-1.267h2.216c.7 0 1.267.567 1.267 1.267V13H12.5V6.543a.07.07 0 0 0-.027-.054L8.038 3.265a.07.07 0 0 0-.078 0L3.527 6.489a.07.07 0 0 0-.027.054zm-1 .467c0 .294.239.533.533.533h3.059a.533.533 0 0 0 .533-.533V9.6c0-.147.12-.267.267-.267h2.216c.148 0 .267.12.267.267v3.867c0 .294.239.533.533.533h3.059a.533.533 0 0 0 .533-.533V6.543c0-.341-.163-.662-.44-.862L8.628 2.456a1.07 1.07 0 0 0-1.254 0L2.939 5.681c-.276.2-.439.52-.439.862z" clipRule="evenodd" />
    </svg>
  );
}
export function OverviewFilled({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" d="M3.033 14a.533.533 0 0 1-.533-.533V6.543c0-.341.163-.662.44-.862l4.433-3.225c.374-.272.88-.272 1.254 0l4.434 3.225c.276.2.439.52.439.862v6.924a.533.533 0 0 1-.533.533H9.908a.533.533 0 0 1-.533-.533V9.6a.267.267 0 0 0-.267-.267H6.892a.267.267 0 0 0-.267.267v3.867a.533.533 0 0 1-.533.533z" />
      <path fill="currentColor" fillRule="evenodd" d="M3.5 13h2.125V9.6c0-.7.567-1.267 1.267-1.267h2.216c.7 0 1.267.567 1.267 1.267V13H12.5V6.543a.07.07 0 0 0-.027-.054L8.038 3.265a.07.07 0 0 0-.078 0L3.527 6.489a.07.07 0 0 0-.027.054zm-1 .467c0 .294.239.533.533.533h3.059a.533.533 0 0 0 .533-.533V9.6c0-.147.12-.267.267-.267h2.216c.148 0 .267.12.267.267v3.867c0 .294.239.533.533.533h3.059a.533.533 0 0 0 .533-.533V6.543c0-.341-.163-.662-.44-.862L8.628 2.456a1.07 1.07 0 0 0-1.254 0L2.939 5.681c-.276.2-.439.52-.439.862z" clipRule="evenodd" />
    </svg>
  );
}

// ── Indexes (folder + magnifier) ────────────────────────────────────────────
export function IndexesDefault({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" d="M7.315 3c.761 0 1.495.289 2.05.809l.02.02a3 3 0 0 0 1.765.794l.285.014H19.5a3 3 0 0 1 3 3V18l-.016.307a3 3 0 0 1-2.677 2.677L19.5 21h-15l-.306-.016A3 3 0 0 1 1.5 18V6a3 3 0 0 1 2.694-2.983L4.5 3zM4.5 4.5A1.5 1.5 0 0 0 3 6v12a1.5 1.5 0 0 0 1.5 1.5h15A1.5 1.5 0 0 0 21 18V7.637a1.5 1.5 0 0 0-1.5-1.5h-8.065A4.5 4.5 0 0 1 8.36 4.924l-.02-.02A1.5 1.5 0 0 0 7.315 4.5zm8.03 3a4.5 4.5 0 1 1-2.607 8.167L7.81 17.78 6.75 16.72l2.112-2.114A4.5 4.5 0 0 1 12.53 7.5m0 1.5a3 3 0 1 0 0 6 3 3 0 0 0 0-6" />
    </svg>
  );
}
export function IndexesFilled({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" d="M7.71 3a2 2 0 0 1 1.366.54l.598.558a2 2 0 0 0 1.365.539H20.5a2 2 0 0 1 2 2V19a2 2 0 0 1-2 2h-17a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zm4.82 4.5a4.5 4.5 0 0 0-3.668 7.106L6.75 16.72l1.06 1.06 2.113-2.113A4.5 4.5 0 1 0 12.53 7.5m0 1.5a3 3 0 1 1 0 6 3 3 0 0 1 0-6" />
    </svg>
  );
}

// ── Assets (folder + plus) ──────────────────────────────────────────────────
export function AssetsDefault({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" d="M21 6.75v10.5a4.5 4.5 0 0 1-4.5 4.5h-9a4.5 4.5 0 0 1-4.5-4.5V6.75a4.5 4.5 0 0 1 4.5-4.5h9zm-13.5-3a3 3 0 0 0-3 3v10.5a3 3 0 0 0 3 3h9a3 3 0 0 0 3-3V9h-2.25A2.25 2.25 0 0 1 15 6.75v-3zM12.757 12H15v1.5h-2.24l.008 2.263-1.5.005-.007-2.268H9V12h2.257l-.007-2.247 1.5-.004zM16.5 6.75c0 .414.336.75.75.75h2.25v-.129z" />
    </svg>
  );
}
export function AssetsFilled({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" d="M21 6v10.5a4.5 4.5 0 0 1-4.5 4.5h-9A4.5 4.5 0 0 1 3 16.5V6a4.5 4.5 0 0 1 4.5-4.5h9zm-9.75 3.003.007 2.247H9v1.5h2.26l.008 2.268 1.5-.005-.007-2.263H15v-1.5h-2.243l-.007-2.251zm3-6.753V6.5a1 1 0 0 0 1 1h5v-.75l-4.5-4.5z" />
    </svg>
  );
}

// ── Entities (folder + person) ──────────────────────────────────────────────
export function EntitiesDefault({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" d="M7.315 3c.761 0 1.495.289 2.05.809l.02.02a3 3 0 0 0 1.765.794l.285.014H19.5a3 3 0 0 1 3 3V18l-.016.307a3 3 0 0 1-2.677 2.677L19.5 21h-15l-.306-.016a3 3 0 0 1-2.677-2.677L1.5 18V6a3 3 0 0 1 2.694-2.983L4.5 3zM4.5 4.5A1.5 1.5 0 0 0 3 6v12a1.5 1.5 0 0 0 1.5 1.5h.906c.24-.844.72-1.943 1.54-2.919C8.007 15.315 9.643 14.25 12 14.25s3.993 1.065 5.056 2.331a8.1 8.1 0 0 1 1.538 2.919h.906A1.5 1.5 0 0 0 21 18V7.637a1.5 1.5 0 0 0-1.5-1.5h-8.065A4.5 4.5 0 0 1 8.36 4.924l-.02-.02A1.5 1.5 0 0 0 7.315 4.5zM12 15.75c-1.843 0-3.081.811-3.906 1.795A6.6 6.6 0 0 0 6.98 19.5h10.04a6.6 6.6 0 0 0-1.113-1.955c-.825-.984-2.064-1.795-3.907-1.795m0-8.25a3 3 0 1 1 0 6 3 3 0 0 1 0-6M12 9a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3" />
    </svg>
  );
}
export function EntitiesFilled({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" d="M7.71 3a2 2 0 0 1 1.366.54l.598.558a2 2 0 0 0 1.365.539H20.5a2 2 0 0 1 2 2V19a2 2 0 0 1-2 2h-17a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zM12 15c-4.2 0-5.75 3-6 4.5h12c-.25-1.5-1.8-4.5-6-4.5m0-7.5a3 3 0 1 0 0 6 3 3 0 0 0 0-6" />
    </svg>
  );
}

// ── Search (magnifier + sparkle) ────────────────────────────────────────────
export function SearchDefault({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" d="M8 2q.36 0 .705.05l-.085.121-.903.84a4 4 0 1 0 4.104 5.173l1.163-.814a4.999 4.999 0 0 1-7.838 3.735L2.885 13.82l-.768-.64 2.27-2.726A5 5 0 0 1 8 2m3.59-.823a.2.2 0 0 1 .366 0l.72 1.594a.2.2 0 0 0 .1.1l1.594.72a.2.2 0 0 1 0 .365l-1.595.72a.2.2 0 0 0-.1.1l-.719 1.594a.2.2 0 0 1-.365 0l-.72-1.594a.2.2 0 0 0-.1-.1l-1.594-.72a.2.2 0 0 1 0-.365l1.595-.72a.2.2 0 0 0 .1-.1z" />
    </svg>
  );
}
export function SearchFilled({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" d="m5.385 10.82-2.5 3-.768-.64 2.5-3z" />
      <path fill="currentColor" d="M8 2c.561 0 1.1.093 1.604.264l-1.457.971a.8.8 0 0 0 .086 1.381l1.577.79a.8.8 0 0 1 .308.27l1.164 1.747a.8.8 0 0 0 1.36-.047l.351-.615Q13 6.88 13 7a5 5 0 1 1-5-5m3.587-.826a.2.2 0 0 1 .365 0l.72 1.594a.2.2 0 0 0 .1.1l1.594.72a.2.2 0 0 1 0 .364l-1.594.72a.2.2 0 0 0-.1.1l-.72 1.594a.2.2 0 0 1-.365 0l-.72-1.593a.2.2 0 0 0-.1-.101l-1.594-.72a.2.2 0 0 1 0-.364l1.595-.72a.2.2 0 0 0 .1-.1z" />
    </svg>
  );
}

// ── Analyze (sparkles) ──────────────────────────────────────────────────────
export function AnalyzeDefault({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" d="M10.747 10.102a.702.702 0 0 1 1.172 0l.052.096.362.801.802.363a.7.7 0 0 1 0 1.276l-.802.362-.362.802a.7.7 0 0 1-1.276 0L10.332 13l-.8-.362a.7.7 0 0 1 0-1.276l.8-.363.363-.8zM4.756 5.135c.354-.784 1.469-.784 1.823 0l.815 1.804 1.803.815c.785.354.785 1.469 0 1.823l-1.803.815-.815 1.803c-.354.785-1.469.785-1.823 0l-.815-1.803-1.804-.815c-.784-.354-.784-1.469 0-1.823L3.94 6.94zm.097 2.215c-.1.222-.279.4-.5.5l-1.804.815 1.804.815c.221.1.4.278.5.5l.814 1.804.815-1.805a1 1 0 0 1 .5-.499l1.804-.815-1.805-.815a1 1 0 0 1-.499-.5l-.815-1.803zm5.895-5.25c.272-.42.9-.42 1.17 0l.054.097.568 1.26 1.263.57a.7.7 0 0 1 0 1.277l-1.262.569-.57 1.262a.7.7 0 0 1-1.276 0l-.57-1.263-1.26-.568a.7.7 0 0 1 0-1.277l1.26-.57.57-1.26zm.243 1.873a.7.7 0 0 1-.35.35l-.76.343.76.343a.7.7 0 0 1 .288.239l.062.11.343.76.343-.76.062-.11a.7.7 0 0 1 .287-.24l.76-.342-.76-.343a.7.7 0 0 1-.35-.35l-.342-.76z" />
    </svg>
  );
}
export function AnalyzeFilled({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" d="M10.747 10.102c.272-.42.9-.421 1.171 0l.053.096.36.801.804.363a.7.7 0 0 1 0 1.277l-.803.361-.361.803a.7.7 0 0 1-1.277 0l-.363-.804-.8-.36a.7.7 0 0 1 0-1.277l.8-.363.363-.8zM4.755 5.137c.354-.785 1.469-.785 1.823 0l.815 1.803 1.803.815c.785.354.785 1.469 0 1.823l-1.803.815-.815 1.803c-.354.785-1.469.785-1.823 0l-.815-1.803-1.803-.815c-.785-.354-.785-1.469 0-1.823L3.94 6.94zm5.992-3.035a.7.7 0 0 1 1.224.096l.569 1.261 1.262.57a.7.7 0 0 1 0 1.276l-1.262.569-.57 1.262a.7.7 0 0 1-1.275 0l-.57-1.262-1.26-.57a.7.7 0 0 1 0-1.275l1.26-.57.57-1.26z" />
    </svg>
  );
}

// ── Segment (rows) ──────────────────────────────────────────────────────────
export function SegmentDefault({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" d="M4 10.5a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1zm9 0a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H6.5a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1zm-6.2 1a.3.3 0 0 0-.3.3v.4a.3.3 0 0 0 .3.3h5.9a.3.3 0 0 0 .3-.3v-.4a.3.3 0 0 0-.3-.3zm-.8-5a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1zm7 0a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H8.5a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1zm-9.7 1a.3.3 0 0 0-.3.3v.4a.3.3 0 0 0 .3.3h2.4a.3.3 0 0 0 .3-.3v-.4a.3.3 0 0 0-.3-.3zm6.2-5a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1zm3.5 0a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1h-1a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1zm-9.7 1a.3.3 0 0 0-.3.3v.4a.3.3 0 0 0 .3.3h5.9a.3.3 0 0 0 .3-.3v-.4a.3.3 0 0 0-.3-.3z" />
    </svg>
  );
}
export function SegmentFilled({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" d="M4 10.5a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1zm9 0a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H6.5a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1zm-7-4a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1zm7 0a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H8.5a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1zm-3.5-4a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1zm3.5 0a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1h-1a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1z" />
    </svg>
  );
}

// ── Examples (shapes) ───────────────────────────────────────────────────────
export function ExamplesDefault({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" fillRule="evenodd" d="M6.116 6h3.768L8 2.918zm4.133 6.751c.393.394.846.582 1.418.582.57 0 1.024-.188 1.418-.582s.582-.846.582-1.418c0-.57-.189-1.024-.582-1.418a1.9 1.9 0 0 0-1.418-.582c-.572 0-1.025.189-1.418.582a1.9 1.9 0 0 0-.582 1.418c0 .572.188 1.025.582 1.418M3 10.267V12.4a.6.6 0 0 0 .6.6h2.133a.6.6 0 0 0 .6-.6v-2.133a.6.6 0 0 0-.6-.6H3.6a.6.6 0 0 0-.6.6m1.83-4.078A.533.533 0 0 0 5.283 7h5.432a.533.533 0 0 0 .455-.811L8.455 1.745a.533.533 0 0 0-.91 0zm4.712 7.27a2.9 2.9 0 0 0 2.125.874q1.25 0 2.125-.875a2.9 2.9 0 0 0 .875-2.125q0-1.25-.875-2.125a2.9 2.9 0 0 0-2.125-.875q-1.25 0-2.125.875a2.9 2.9 0 0 0-.875 2.125q0 1.25.875 2.125M2 12.4A1.6 1.6 0 0 0 3.6 14h2.133a1.6 1.6 0 0 0 1.6-1.6v-2.133a1.6 1.6 0 0 0-1.6-1.6H3.6a1.6 1.6 0 0 0-1.6 1.6z" clipRule="evenodd" />
    </svg>
  );
}
export function ExamplesFilled({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" d="M5.284 7a.533.533 0 0 1-.455-.811l2.716-4.444a.533.533 0 0 1 .91 0l2.716 4.444a.533.533 0 0 1-.455.811zm6.383 7.333a2.9 2.9 0 0 1-2.125-.875 2.9 2.9 0 0 1-.875-2.125q0-1.25.875-2.125a2.9 2.9 0 0 1 2.125-.875q1.25 0 2.125.875.875.876.875 2.125t-.875 2.125a2.9 2.9 0 0 1-2.125.875M3.6 14A1.6 1.6 0 0 1 2 12.4v-2.133a1.6 1.6 0 0 1 1.6-1.6h2.133a1.6 1.6 0 0 1 1.6 1.6V12.4a1.6 1.6 0 0 1-1.6 1.6z" />
    </svg>
  );
}

// ── API Keys (padlock) ──────────────────────────────────────────────────────
export function APIKeysDefault({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" fillRule="evenodd" d="M6.5 1.5a3 3 0 0 0-3 3V6A1.5 1.5 0 0 0 2 7.5v5A1.5 1.5 0 0 0 3.5 14h9a1.5 1.5 0 0 0 1.5-1.5v-5A1.5 1.5 0 0 0 12.5 6V4.5a3 3 0 0 0-3-3zm5 4.5V4.5a2 2 0 0 0-2-2h-3a2 2 0 0 0-2 2V6zm-8 1a.5.5 0 0 0-.5.5v5a.5.5 0 0 0 .5.5h9a.5.5 0 0 0 .5-.5v-5a.5.5 0 0 0-.5-.5h-9M7 10a1 1 0 1 1 2 0 1 1 0 0 1-2 0" clipRule="evenodd" />
    </svg>
  );
}

// ── Settings (sliders) ──────────────────────────────────────────────────────
export function SettingsDefault({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" fillRule="evenodd" d="M8 4.25H2v-1h6zm6 0h-2v-1h2zM6.667 12.25H2v-1h4.667zm7.333 0h-3.333v-1H14zM8 7.25h6v1H8zm-6 0h2v1H2zM9.668 3.417v.666h.667v-.666zm-.2-1a.8.8 0 0 0-.8.8v1.066a.8.8 0 0 0 .8.8h1.067a.8.8 0 0 0 .8-.8V3.217a.8.8 0 0 0-.8-.8zM5.668 7.417v.666h.667v-.666zm-.2-1a.8.8 0 0 0-.8.8v1.066a.8.8 0 0 0 .8.8h1.067a.8.8 0 0 0 .8-.8V7.217a.8.8 0 0 0-.8-.8zM8.334 11.417v.666h.667v-.666zm-.2-1a.8.8 0 0 0-.8.8v1.066a.8.8 0 0 0 .8.8h1.067a.8.8 0 0 0 .8-.8v-1.066a.8.8 0 0 0-.8-.8z" clipRule="evenodd" />
    </svg>
  );
}

// ── API Docs (book) ─────────────────────────────────────────────────────────
export function APIDocsDefault({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" width={size} height={size} className={className ?? BASE}>
      <path stroke="currentColor" d="M3.5 12.5a1 1 0 0 0 1 1H12a.5.5 0 0 0 .5-.5v-1.5h-8a1 1 0 0 0-1 1Z" />
      <path fill="currentColor" fillRule="evenodd" d="M3.085 13H3V4a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v9a1 1 0 0 1-1 1H4.5a1.5 1.5 0 0 1-1.415-1M4 12.5a.5.5 0 0 0 .5.5H12v-1H4.5a.5.5 0 0 0-.5.5m8-1.5V4a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v7.085q.236-.084.5-.085zM6 5h4v1H6zm3 2H6v1h3z" clipRule="evenodd" />
    </svg>
  );
}

// ── Help (?) ────────────────────────────────────────────────────────────────
export function HelpDefault({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" fillRule="evenodd" d="M10.4 3H5.6A2.6 2.6 0 0 0 3 5.6v4.8A2.6 2.6 0 0 0 5.6 13h4.8a2.6 2.6 0 0 0 2.6-2.6V5.6A2.6 2.6 0 0 0 10.4 3M5.6 2A3.6 3.6 0 0 0 2 5.6v4.8A3.6 3.6 0 0 0 5.6 14h4.8a3.6 3.6 0 0 0 3.6-3.6V5.6A3.6 3.6 0 0 0 10.4 2z" clipRule="evenodd" />
      <path fill="currentColor" d="M6.987 11.333c0-.216.117-.333.333-.333h.657c.216 0 .333.117.333.333V12c0 .216-.117.333-.333.333H7.32c-.216 0-.333-.117-.333-.333zm.99-7.479c1.536 0 2.596.98 2.596 2.414 0 1.425-1.04 2.37-2.417 2.393v.672c0 .216-.117.334-.333.334h-.36c-.216 0-.333-.117-.333-.334V8.042c0-.216.117-.334.334-.334h.513c.875 0 1.55-.515 1.55-1.44 0-.909-.67-1.424-1.55-1.424-.868 0-1.519.479-1.555 1.37-.008.224-.104.343-.323.343h-.383c-.21 0-.341-.112-.341-.325-.005-1.417 1.057-2.378 2.602-2.378" />
    </svg>
  );
}

// ── Collapse (panel) ────────────────────────────────────────────────────────
export function CollapseDefault({ size = 24, className }: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 16 16" width={size} height={size} className={className ?? BASE}>
      <path fill="currentColor" fillRule="evenodd" d="M7.167 3v10H10.4a2.6 2.6 0 0 0 2.6-2.6V5.6A2.6 2.6 0 0 0 10.4 3zm-1 0v10H5.6A2.6 2.6 0 0 1 3 10.4V5.6A2.6 2.6 0 0 1 5.6 3zM5.6 2A3.6 3.6 0 0 0 2 5.6v4.8A3.6 3.6 0 0 0 5.6 14h4.8a3.6 3.6 0 0 0 3.6-3.6V5.6A3.6 3.6 0 0 0 10.4 2z" clipRule="evenodd" />
      <path fill="currentColor" fillRule="evenodd" d="m8.785 7.175 1.529-1.529.707.708-1.529 1.528a.167.167 0 0 0 0 .236l1.529 1.528-.707.708-1.529-1.529a1.167 1.167 0 0 1 0-1.65" clipRule="evenodd" />
    </svg>
  );
}
