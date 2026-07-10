import { useEffect, useState } from "react";
import { TopBar } from "./components/TopBar";
import { Autopilot } from "./pages/Autopilot";
import { Library } from "./pages/Library";
import { Pipeline } from "./pages/Pipeline";
import { Today } from "./pages/Today";

// v2 shell: three surfaces (Today / Pipeline / Library), no sidebar.
// Old deep links (#/company/X, #/desk, #/screener…) redirect into Library.

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
  [/^\/company\/(.+)$/, (m) => `/library/company/${m[1]}`],
  [/^\/desk(\/.+)?$/, (m) => `/library/desk${m[1] ?? ""}`.replace(/\/$/, "")],
  [/^\/(research|screener|risk|lab)$/, (m) => `/library/${m[1] === "research" ? "dossiers" : m[1]}`],
];

export function App() {
  let route = useRoute();
  for (const [re, to] of LEGACY) {
    const m = route.match(re);
    if (m) { route = to(m); window.location.hash = `#${route}`; break; }
  }

  let page: JSX.Element;
  if (route.startsWith("/autopilot")) page = <Autopilot />;
  else if (route.startsWith("/pipeline")) page = <Pipeline />;
  else if (route.startsWith("/library")) page = <Library route={route} />;
  else page = <Today />;

  return (
    <div className="shell2">
      <TopBar route={route} />
      <main className="main">{page}</main>
    </div>
  );
}
