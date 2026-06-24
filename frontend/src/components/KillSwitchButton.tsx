export function KillSwitchButton({ stopped, onChange }: { stopped: boolean; onChange: (stopped: boolean) => void }) {
  return (
    <button
      type="button"
      className={`kill-switch ${stopped ? "is-stopped" : ""}`}
      onClick={() => onChange(!stopped)}
      aria-pressed={stopped}
      aria-label={stopped ? "긴급 정지 해제" : "긴급 정지 활성화"}
    >
      <span className="stop-icon">■</span>
      <span><small>{stopped ? "STOP ACTIVE" : "EMERGENCY"}</small>{stopped ? "정지 해제" : "긴급 STOP"}</span>
    </button>
  );
}

