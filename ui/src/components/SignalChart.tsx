import {
  ColorType, createChart, CrosshairMode, IChartApi, LineStyle, SeriesMarker, Time,
} from "lightweight-charts";
import { useEffect, useRef } from "react";

// Chart-first, Trade-with-Jarvis style: candlesticks with a green/red trend
// cloud (price vs its long-term average), a fast moving average, volume, and
// the engine's BUY/SELL marked directly on the price.

export interface Candle { time: string; open: number; high: number; low: number; close: number; volume: number; }
export interface ChartMarker { time: string; side: "BUY" | "SELL"; text: string; }
export interface ForecastBand { low1: number; high1: number; low2: number; high2: number; }

function sma(data: Candle[], period: number): { time: string; value: number }[] {
  const out: { time: string; value: number }[] = [];
  for (let i = period - 1; i < data.length; i++) {
    let s = 0;
    for (let j = i - period + 1; j <= i; j++) s += data[j].close;
    out.push({ time: data[i].time, value: s / period });
  }
  return out;
}

export function SignalChart({ data, markers, band, height = 400 }: { data: Candle[]; markers?: ChartMarker[]; band?: ForecastBand | null; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!ref.current || !data.length) return;
    const up = "#16C784", down = "#F0616D", grid = "rgba(255,255,255,.04)", txt = "#7c8a9c";

    const chart = createChart(ref.current, {
      height,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: txt,
        fontFamily: "'JetBrains Mono', Consolas, monospace", fontSize: 11 },
      grid: { vertLines: { color: grid }, horzLines: { color: grid } },
      crosshair: { mode: CrosshairMode.Normal,
        vertLine: { color: "rgba(255,255,255,.2)", labelBackgroundColor: "#1b2430" },
        horzLine: { color: "rgba(255,255,255,.2)", labelBackgroundColor: "#1b2430" } },
      rightPriceScale: { borderColor: "rgba(255,255,255,.06)" },
      timeScale: { borderColor: "rgba(255,255,255,.06)", timeVisible: false, rightOffset: 4 },
      autoSize: true,
    });
    chartRef.current = chart;

    const ma200 = data.length >= 200
      ? data.slice(-200).reduce((s, c) => s + c.close, 0) / 200
      : data.reduce((s, c) => s + c.close, 0) / data.length;

    // trend cloud: area of price shaded green above / red below its long-term average
    const cloud = chart.addBaselineSeries({
      baseValue: { type: "price", price: ma200 },
      topLineColor: "rgba(22,199,132,.55)", topFillColor1: "rgba(22,199,132,.16)", topFillColor2: "rgba(22,199,132,.02)",
      bottomLineColor: "rgba(240,97,109,.55)", bottomFillColor1: "rgba(240,97,109,.02)", bottomFillColor2: "rgba(240,97,109,.16)",
      lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
    });
    cloud.setData(data.map((c) => ({ time: c.time as Time, value: c.close })));

    const candles = chart.addCandlestickSeries({
      upColor: up, downColor: down, wickUpColor: up, wickDownColor: down, borderVisible: false,
      priceLineVisible: true, priceLineColor: "rgba(255,255,255,.25)", priceLineStyle: LineStyle.Dotted,
    });
    candles.setData(data.map(({ volume, ...c }) => ({ ...c, time: c.time as Time })));

    const ma50 = chart.addLineSeries({ color: "rgba(120,170,255,.8)", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    ma50.setData(sma(data, 50).map((p) => ({ ...p, time: p.time as Time })));

    const vol = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol" });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.86, bottom: 0 } });
    vol.setData(data.map((c) => ({ time: c.time as Time, value: c.volume, color: c.close >= c.open ? up + "33" : down + "33" })));

    if (markers?.length) {
      const ms: SeriesMarker<Time>[] = markers.map((m) => ({
        time: m.time as Time,
        position: m.side === "BUY" ? "belowBar" : "aboveBar",
        color: m.side === "BUY" ? up : down,
        shape: m.side === "BUY" ? "arrowUp" : "arrowDown",
        text: m.text,
      }));
      ms.sort((a, b) => (a.time < b.time ? -1 : 1));
      candles.setMarkers(ms);
    }

    // forecast: the likely range next month, drawn as horizon lines
    if (band) {
      const mk = (price: number, title: string, alpha: string) => candles.createPriceLine({
        price, color: `rgba(120,170,255,${alpha})`, lineWidth: 1, lineStyle: LineStyle.Dashed,
        axisLabelVisible: true, title,
      });
      mk(band.high1, "likely high", ".7");
      mk(band.low1, "likely low", ".7");
      mk(band.high2, "", ".3");
      mk(band.low2, "", ".3");
    }

    chart.timeScale().fitContent();
    return () => { chart.remove(); chartRef.current = null; };
  }, [data, markers, band, height]);

  if (!data.length) return <div style={{ height, display: "grid", placeItems: "center", color: "#5f6b7c", fontSize: 12 }}>no chart data</div>;
  return <div ref={ref} style={{ width: "100%" }} />;
}
