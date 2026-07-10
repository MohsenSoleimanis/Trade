import { ColorType, createChart, CrosshairMode, IChartApi } from "lightweight-charts";
import { useEffect, useRef } from "react";

// Terminal-grade candlestick + volume chart (TradingView's open-source
// lightweight-charts). Raw daily OHLC — candles show what you'd actually
// have paid on the day; the line view stays for adjusted long-horizon reads.

export interface Candle {
  time: string; open: number; high: number; low: number; close: number; volume: number;
}

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function CandleChart({ data, wrongPrice }: { data: Candle[]; wrongPrice?: number | null }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!ref.current || !data.length) return;

    const ink = cssVar("--ink") || "#e7edea";
    const muted = cssVar("--muted") || "#8fa198";
    const grid = cssVar("--grid") || "#222b26";
    const green = cssVar("--green") || "#199e70";
    const red = cssVar("--red") || "#e66767";

    const chart = createChart(ref.current, {
      height: 360,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: muted,
        fontFamily: "Consolas, 'Cascadia Mono', monospace",
        fontSize: 11,
      },
      grid: { vertLines: { color: grid }, horzLines: { color: grid } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: grid },
      timeScale: { borderColor: grid, timeVisible: false },
      autoSize: true,
    });
    chartRef.current = chart;

    const candles = chart.addCandlestickSeries({
      upColor: green, downColor: red,
      wickUpColor: green, wickDownColor: red,
      borderVisible: false,
    });
    candles.setData(data.map(({ volume, ...c }) => c));

    const vol = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
      color: muted,
    });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    vol.setData(data.map((c) => ({
      time: c.time, value: c.volume,
      color: c.close >= c.open ? green + "55" : red + "55",
    })));

    if (wrongPrice) {
      candles.createPriceLine({
        price: wrongPrice, color: red, lineWidth: 1, lineStyle: 2,
        axisLabelVisible: true, title: "your exit",
      });
    }

    chart.timeScale().fitContent();
    const obs = new ResizeObserver(() => chart.applyOptions({}));
    obs.observe(ref.current);
    return () => { obs.disconnect(); chart.remove(); chartRef.current = null; };
  }, [data, wrongPrice]);

  if (!data.length) return <div className="loading">no OHLC history</div>;
  return <div ref={ref} style={{ width: "100%" }} />;
}
