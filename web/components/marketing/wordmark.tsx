/**
 * The AccountIQ wordmark. The tail of the Q is the reviewer's red tick: every
 * report is checked before it goes out, and the name says so.
 */
export function Wordmark() {
  return (
    <span className="wordmark" aria-hidden="true">
      AccountI
      <svg className="wordmark-q" viewBox="0 0 32 28" focusable="false">
        <circle cx="12.5" cy="13.5" r="10.4" fill="none" stroke="currentColor" strokeWidth="4.3" />
        <path
          className="wordmark-tick"
          d="M14.2 17.6 L19 24 L30.5 4.5"
          fill="none"
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}
