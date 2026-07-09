import { useEffect, useState } from "react";
import { Company } from "./pages/Company";
import { Dashboard } from "./pages/Dashboard";
import { Research } from "./pages/Research";

// Hash-based routing, zero dependencies: #/research, #/company/LOTB …
// The FastAPI static mount serves index.html for "/", the hash does the rest.

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
  // [label, route ("" = not built yet), phase]
  ["Dashboard", "/", "now"],
  ["Research", "/research", "now"],
  ["Screener", "", "ph 5"],
  ["Risk Console", "", "ph 3"],
  ["Trading Desk", "", "ph 3"],
  ["Backtest Lab", "", "ph 4"],
  ["Agent Floor", "", "ph 6"],
];

export function App() {
  const route = useRoute();

  let page: JSX.Element;
  if (route.startsWith("/company/")) page = <Company symbol={route.split("/")[2]} />;
  else if (route === "/research") page = <Research />;
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
      <main className="main">{page}</main>
    </div>
  );
}

function routeMatches(route: string, to: string) {
  if (to === "/") return route === "/";
  if (to === "/research") return route === "/research" || route.startsWith("/company/");
  return route.startsWith(to);
}
