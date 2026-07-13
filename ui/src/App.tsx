import { useEffect, useState } from "react";
import { TopBar } from "./components/TopBar";
import { AutoEngine } from "./pages/AutoEngine";
import { EngineConsole } from "./pages/EngineConsole";
import { Autopilot } from "./pages/Autopilot";
import { Library } from "./pages/Library";
import { Pipeline } from "./pages/Pipeline";
import { Today } from "./pages/Today";
import { Workspace } from "./pages/Workspace";

// UX v3: the WORKSPACE is the app. Everything else is secondary,
// reachable through the ▤ menu (skill rule: primary vs secondary nav).

function useRoute(): string {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const fn = () => setHash(window.location.hash);
    window.addEventListener("hashchange", fn);
    return () => window.removeEventListener("hashchange", fn);
  }, []);
  return hash.replace(/^#/, "") || "/";
}

const LEGACY: [RegExp, (m: RegExpMatchArray) => string][] = [
  [/^\/company\/(.+)$/, (m) => `/w/${m[1]}`],
  [/^\/desk(\/(.+))?$/, (m) => (m[2] ? `/w/${m[2]}` : "/library/desk")],
  [/^\/(research|screener|risk|lab)$/, (m) => `/library/${m[1] === "research" ? "dossiers" : m[1]}`],
];

export function App() {
  let route = useRoute();
  for (const [re, to] of LEGACY) {
    const m = route.match(re);
    if (m) { route = to(m); window.location.hash = `#${route}`; break; }
  }

  let page: JSX.Element;
  if (route.startsWith("/w/")) page = <Workspace initial={route.split("/")[2]} />;
  else if (route.startsWith("/engine/classic")) page = <div className="page-pad"><AutoEngine /></div>;
  else if (route.startsWith("/engine")) page = <EngineConsole />;
  else if (route.startsWith("/autopilot")) page = <Autopilot />;
  else if (route.startsWith("/pipeline")) page = <Pipeline />;
  else if (route.startsWith("/today")) page = <Today />;
  else if (route.startsWith("/library")) page = <div className="page-pad"><Library route={route} /></div>;
  else page = <Workspace />;

  const isWorkspace = route === "/" || route.startsWith("/w/");
  return (
    <div className="shell2">
      <TopBar route={route} />
      {isWorkspace ? page : <main className="main">{page}</main>}
    </div>
  );
}
