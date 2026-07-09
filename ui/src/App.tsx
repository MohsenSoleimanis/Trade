import { useEffect, useState } from "react";
import { TopBar } from "./components/TopBar";
import { Company } from "./pages/Company";
import { Dashboard } from "./pages/Dashboard";
import { Research } from "./pages/Research";
import { RiskConsole } from "./pages/RiskConsole";
import { TradingDesk } from "./pages/TradingDesk";

function useRoute(): string {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const fn = () => setHash(window.location.hash);
    window.addEventListener("hashchange", fn);
    return () => window.removeEventListener("hashchange", fn);
  }, []);
  return hash.replace(/^#/, "") || "/";
}

const MODULES: [string, string, string][] = [
  ["Dashboard", "/", ""],
  ["Research", "/research", ""],
  ["Screener", "", "ph 5"],
  ["Risk Console", "/risk", ""],
  ["Trading Desk", "/desk", ""],
  ["Backtest Lab", "", "ph 4"],
  ["Agent Floor", "", "ph 6"],
];

export function App() {
  const route = useRoute();

  let page: JSX.Element;
  if (route.startsWith("/company/")) page = <Company symbol={route.split("/")[2]} />;
  else if (route === "/research") page = <Research />;
  else if (route === "/risk") page = <RiskConsole />;
  else if (route.startsWith("/desk")) page = <TradingDesk route={route} />;
  else page = <Dashboard />;

  return (
    <div className="shell">
      <nav className="sidenav">
        <a className="brand" href="#/">⚖ De Waag<span className="v">v0.1</span></a>
        {MODULES.map(([label, to, phase]) =>
          to ? (
            <a key={label} className={`nav ${routeMatches(route, to) ? "on" : ""}`} href={`#${to}`}>
              {label}
            </a>
          ) : (
            <a key={label} className="nav off" aria-disabled="true">
              {label}<span className="phase">{phase}</span>
            </a>
          )
        )}
      </nav>
      <div className="content">
        <TopBar />
        <main className="main">{page}</main>
      </div>
    </div>
  );
}

function routeMatches(route: string, to: string) {
  if (to === "/") return route === "/";
  if (to === "/research") return route === "/research" || route.startsWith("/company/");
  return route.startsWith(to);
}
