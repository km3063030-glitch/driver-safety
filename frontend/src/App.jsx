import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api.js";

const TOKEN_KEY = "driver-safety-token";
const fmt = (value, digits = 1) => Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "—";

function Login({ onLogin }) {
  const [username, setUsername] = useState("manager1");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api.login(username.trim(), password);
      onLogin(result.access_token);
    } catch (err) {
      setError(err.message || "Unable to sign in");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-card">
        <div className="brand-mark">R</div>
        <p className="eyebrow">FLEET INTELLIGENCE</p>
        <h1>Drive safer, together.</h1>
        <p className="muted">Sign in to view your fleet's safety signals.</p>
        <form onSubmit={submit} className="stack-form">
          <label>Username<input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required /></label>
          <label>Password<input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
          {error && <p className="inline-error" role="alert">{error}</p>}
          <button className="primary-button" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>
        <p className="login-foot">Access is limited to your authenticated fleet.</p>
      </section>
    </main>
  );
}

function Metric({ label, value, detail }) {
  return <article className="metric-card"><span className="muted">{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article>;
}

function ScorePill({ score }) {
  const value = Number(score);
  const tone = value < 45 ? "danger" : value < 60 ? "warning" : "good";
  return <span className={`score-pill ${tone}`}>{fmt(score, 1)}</span>;
}

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY));
  const [active, setActive] = useState("overview");
  const [order, setOrder] = useState("worst");
  const [leaderboard, setLeaderboard] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [selectedVin, setSelectedVin] = useState(null);
  const [detail, setDetail] = useState(null);
  const [similar, setSimilar] = useState([]);
  const [question, setQuestion] = useState("");
  const [chat, setChat] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const signIn = (value) => {
    sessionStorage.setItem(TOKEN_KEY, value);
    setToken(value);
  };
  const signOut = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setLeaderboard([]);
    setAlerts([]);
    setSelectedVin(null);
    setDetail(null);
    setChat([]);
  }, []);

  const refresh = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const [board, alertData] = await Promise.all([
        api.leaderboard(token, order),
        api.alerts(token),
      ]);
      setLeaderboard(board.items || []);
      setAlerts(alertData.items || []);
      setError("");
    } catch (err) {
      setError(err.message || "Could not load fleet data");
      if (/401|invalid|expired/i.test(err.message || "")) signOut();
    } finally {
      setLoading(false);
    }
  }, [token, order, signOut]);

  useEffect(() => {
    refresh();
    if (!token) return undefined;
    const timer = window.setInterval(refresh, 15000);
    return () => window.clearInterval(timer);
  }, [refresh, token]);

  useEffect(() => {
    if (!token || !selectedVin) return;
    let live = true;
    Promise.all([api.vehicle(token, selectedVin), api.similar(token, selectedVin)])
      .then(([vehicle, neighbors]) => {
        if (!live) return;
        setDetail(vehicle);
        setSimilar(neighbors.similar || []);
      })
      .catch((err) => live && setError(err.message || "Could not load vehicle"));
    return () => { live = false; };
  }, [token, selectedVin]);

  const averageScore = useMemo(() => leaderboard.length
    ? (leaderboard.reduce((sum, row) => sum + Number(row.score || 0), 0) / leaderboard.length).toFixed(1)
    : "—", [leaderboard]);
  const lowScoreCount = leaderboard.filter((row) => Number(row.score) < 45).length;

  async function sendQuestion(event) {
    event.preventDefault();
    const text = question.trim();
    if (text.length < 3 || busy) return;
    setChat((items) => [...items, { role: "you", text }]);
    setQuestion("");
    setBusy(true);
    try {
      const result = await api.ask(token, text);
      setChat((items) => [...items, { role: "assistant", text: result.answer }]);
    } catch (err) {
      setChat((items) => [...items, { role: "assistant", text: `Request failed: ${err.message}` }]);
    } finally {
      setBusy(false);
    }
  }

  if (!token) return <Login onLogin={signIn} />;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark small">R</span><span>roadwise<small>FLEET SAFETY</small></span></div>
        <div className="fleet-label"><span className="online-dot" /> YOUR FLEET</div>
        <nav aria-label="Main navigation">
          <button className={active === "overview" ? "nav-item selected" : "nav-item"} aria-label="Overview" title="Overview" onClick={() => { setActive("overview"); setSelectedVin(null); }}>◫ <span>Overview</span></button>
          <button className={active === "vehicles" ? "nav-item selected" : "nav-item"} aria-label="Vehicles" title="Vehicles" onClick={() => { setActive("vehicles"); setSelectedVin(null); }}>▤ <span>Vehicles</span></button>
          <button className={active === "alerts" ? "nav-item selected" : "nav-item"} aria-label="Alerts" title="Alerts" onClick={() => { setActive("alerts"); setSelectedVin(null); }}>◉ <span>Alerts</span><b>{alerts.length}</b></button>
          <button className={active === "assistant" ? "nav-item selected" : "nav-item"} aria-label="Safety copilot" title="Safety copilot" onClick={() => { setActive("assistant"); setSelectedVin(null); }}>✳ <span>Safety copilot</span></button>
        </nav>
        <div className="sidebar-bottom"><div className="avatar">FM</div><div><strong>Fleet manager</strong><small>Authenticated session</small></div><button className="signout" onClick={signOut} aria-label="Sign out" title="Sign out">↗</button></div>
      </aside>

      <main className="main-content">
        <header className="topbar"><div><p className="eyebrow">DRIVER SAFETY / {active.toUpperCase()}</p><h1>{selectedVin ? "Vehicle profile" : active === "overview" ? "Fleet overview" : active === "vehicles" ? "Vehicles" : active === "alerts" ? "Recent alerts" : "Safety copilot"}</h1></div><div className="top-actions"><span className="live-indicator"><i /> Live data</span><button className="icon-button" onClick={refresh} disabled={loading} title="Refresh">↻</button></div></header>
        {error && <div className="error-banner" role="alert">{error}<button onClick={() => setError("")} aria-label="Dismiss">×</button></div>}

        {selectedVin ? (
          <VehicleView vin={selectedVin} detail={detail} similar={similar} onBack={() => { setSelectedVin(null); setDetail(null); }} />
        ) : active === "assistant" ? (
          <section className="assistant-layout">
            <div className="assistant-intro"><div className="assistant-icon">✳</div><p className="eyebrow">GEMINI-POWERED</p><h2>Your fleet safety copilot</h2><p className="muted">Ask grounded questions about scores, alerts, and similar vehicles in your fleet.</p><div className="suggestions"><button onClick={() => setQuestion("Which vehicles have the lowest safety scores?")}>Which vehicles need attention?</button><button onClick={() => setQuestion("Explain the latest safety alerts")}>Explain recent alerts</button></div></div>
            <div className="chat-panel"><div className="chat-log" aria-live="polite">{chat.length === 0 && <div className="empty-chat">Ask about your fleet. Answers use fleet-scoped data and are audited.</div>}{chat.map((item, index) => <div key={`${index}-${item.role}`} className={`chat-message ${item.role}`}><span>{item.role === "you" ? "You" : "Copilot"}</span><p>{item.text}</p></div>)}{busy && <div className="chat-message assistant"><span>Copilot</span><p>Checking fleet data…</p></div>}</div><form className="chat-form" onSubmit={sendQuestion}><textarea value={question} onChange={(e) => setQuestion(e.target.value)} minLength={3} maxLength={500} placeholder="Ask a fleet safety question…" aria-label="Question" /><button className="primary-button" disabled={busy || question.trim().length < 3}>{busy ? "Working…" : "Ask"}</button></form><small className="muted">Responses can be imperfect. Verify important decisions against source data.</small></div>
          </section>
        ) : active === "alerts" ? (
          <AlertsView alerts={alerts} onSelect={(vin) => { setSelectedVin(vin); setActive("vehicles"); }} />
        ) : (
          <>
            {active === "overview" && <section className="metrics-grid"><Metric label="Vehicles with recent scores" value={leaderboard.length.toLocaleString()} detail="Last 7 days" /><Metric label="Average safety score" value={averageScore} detail="Higher is safer" /><Metric label="Needs attention" value={lowScoreCount.toLocaleString()} detail="Score below 45" /><Metric label="Open recent alerts" value={alerts.length.toLocaleString()} detail="Latest 30 alerts" /></section>}
            <section className="panel">
              <div className="panel-heading"><div><p className="eyebrow">FLEET PERFORMANCE</p><h2>{active === "overview" ? "Vehicles to watch" : "All scored vehicles"}</h2></div><div className="panel-actions"><select value={order} onChange={(e) => setOrder(e.target.value)} aria-label="Sort leaderboard"><option value="worst">Lowest score first</option><option value="best">Highest score first</option></select><button className="text-button" onClick={() => setActive("alerts")}>View alerts →</button></div></div>
              <Leaderboard rows={active === "overview" ? leaderboard.slice(0, 8) : leaderboard} loading={loading} onSelect={(vin) => { setSelectedVin(vin); setActive("vehicles"); }} />
              {active === "overview" && <button className="wide-link" onClick={() => setActive("vehicles")}>View all vehicles →</button>}
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function Leaderboard({ rows, loading, onSelect }) {
  return <div className="table-wrap"><table><thead><tr><th>Vehicle</th><th>Driver</th><th>Score</th><th>Distance</th><th>Harsh brake</th><th>Overspeed</th></tr></thead><tbody>
    {rows.map((row) => <tr key={row.vin} onClick={() => onSelect(row.vin)} tabIndex="0" onKeyDown={(event) => event.key === "Enter" && onSelect(row.vin)}><td><button className="vin-link" onClick={(event) => { event.stopPropagation(); onSelect(row.vin); }}>{row.vin}</button></td><td>{row.driver_id || "—"}</td><td><ScorePill score={row.score} /></td><td>{fmt(row.km)} km</td><td>{row.hb ?? 0}</td><td>{row.os ?? 0}</td></tr>)}
    {rows.length === 0 && <tr><td colSpan="6" className="empty-row">{loading ? "Loading fleet data…" : "No scored vehicles yet. Start the ingest pipeline and simulator."}</td></tr>}
  </tbody></table></div>;
}

function AlertsView({ alerts, onSelect }) {
  return <section className="panel"><div className="panel-heading"><div><p className="eyebrow">RECENT ACTIVITY</p><h2>Safety alerts</h2></div><span className="muted">Newest first</span></div><div className="alerts-list">{alerts.map((alert, index) => <article className="alert-row" key={`${alert.vin}-${alert.raised_at}-${index}`}><span className={`severity ${String(alert.severity).toLowerCase()}`}>{alert.severity}</span><div className="alert-main"><button className="vin-link" onClick={() => onSelect(alert.vin)}>{alert.vin}</button><p>{alert.rule?.replaceAll("_", " ") || "Safety event"}</p></div><time>{alert.raised_at ? new Date(alert.raised_at).toLocaleString() : "—"}</time><span className="alert-detail">{alert.details?.count ? `${alert.details.count} events` : "View vehicle"}</span></article>)}{alerts.length === 0 && <div className="empty-row">No recent alerts for this fleet.</div>}</div></section>;
}

function VehicleView({ vin, detail, similar, onBack }) {
  const score = detail?.score;
  return <section className="vehicle-page"><button className="text-button back-button" onClick={onBack}>← Back to fleet</button>{!detail ? <div className="panel empty-row">Loading vehicle profile…</div> : <><div className="vehicle-heading"><div><p className="eyebrow">VEHICLE PROFILE</p><h2>{vin}</h2><p className="muted">Driver {detail.driver_id || "—"}</p></div><ScorePill score={score?.score} /></div><div className="metrics-grid vehicle-metrics"><Metric label="Safety score" value={fmt(score?.score)} detail="Higher is safer" /><Metric label="Distance observed" value={`${fmt(score?.km)} km`} detail="Recent scoring window" /><Metric label="Harsh braking" value={score?.hb ?? "—"} detail="Events" /><Metric label="Overspeeding" value={score?.os ?? "—"} detail="Events" /></div><div className="detail-grid"><section className="panel"><div className="panel-heading"><div><p className="eyebrow">RECENT ACTIVITY</p><h2>Vehicle alerts</h2></div></div><AlertsView alerts={detail.alerts || []} onSelect={() => {}} /></section><section className="panel"><div className="panel-heading"><div><p className="eyebrow">BEHAVIOR MATCH</p><h2>Similar vehicles</h2></div></div>{similar.length ? similar.map((row) => <div className="neighbor-row" key={row.vin}><span>{row.vin}</span><small>Distance {fmt(row.distance, 3)}</small>{row.score != null && <ScorePill score={row.score} />}</div>) : <p className="muted">No similar vehicle profiles found in this fleet.</p>}</section></div></>}</section>;
}

export default App;
