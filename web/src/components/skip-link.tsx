/**
 * First-focus control: jumps past sticky nav to primary content.
 * Visually hidden until keyboard focus (WCAG 2.4.1).
 */
export function SkipLink() {
  return (
    <a href="#main-content" className="chime-skip-link">
      Skip to content
    </a>
  );
}
