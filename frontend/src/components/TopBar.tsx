import logo from "../assets/StormHaul.jpg";

interface TopBarProps {
  onReset: () => void;
  dataSource?: string;
  busy: boolean;
}

export function TopBar({ onReset, dataSource, busy }: TopBarProps) {
  return (
    <header className="topbar">
      <div className="brand">
        <img className="brand-logo" src={logo} alt="StormHaul" />
        <div>
          <h1>StormHaul</h1>
          <p>Weather-aware truck routing</p>
        </div>
      </div>
      <div className="topbar-actions">
        <span className={`status-pill ${busy ? "is-busy" : ""}`}>
          {busy ? "Planning..." : dataSource ? `Routing: ${dataSource}` : "Idle"}
        </span>
        <button type="button" className="ghost-button" onClick={onReset}>
          Reset
        </button>
      </div>
    </header>
  );
}
