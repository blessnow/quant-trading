"use client";

import { useState, useRef } from "react";

interface DataPoint {
  market: string;
  total_value: number;
  date: string;
  time?: string;
}

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

export function EquityChart({ data }: { data: DataPoint[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [hovered, setHovered] = useState<{
    mouseX: number;
    mouseY: number;
    containerW: number;
    date: string;
    svgX: number;
    aShare?: number;
    usStock?: number;
  } | null>(null);

  const dedupeByDate = (arr: DataPoint[]) => {
    const byDate: Record<string, DataPoint> = {};
    arr.forEach((d) => { byDate[d.date] = d; });
    return Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date));
  };

  const aShare = dedupeByDate(data.filter((d) => d.market === "A_SHARE"));
  const usStock = dedupeByDate(data.filter((d) => d.market === "US_STOCK"));
  const allVals = [...aShare, ...usStock].map((d) => d.total_value);
  if (allVals.length === 0) return null;
  const minV = Math.min(...allVals) * 0.995;
  const maxV = Math.max(...allVals) * 1.005;
  const range = maxV - minV || 1;
  const w = 800, h = 240, px = 55, py = 15;
  const chartW = w - 2 * px;

  const getX = (arr: DataPoint[], i: number) => {
    if (arr.length === 1) return (px + w - px) / 2;
    return px + (i / (arr.length - 1)) * (w - 2 * px);
  };

  const getY = (d: DataPoint) =>
    h - py - ((d.total_value - minV) / range) * (h - 2 * py);

  const pts = (arr: DataPoint[]) =>
    arr.map((d, i) => `${getX(arr, i)},${getY(d)}`).join(" ");

  const aShareByDate: Record<string, { value: number; x: number; y: number }> = {};
  aShare.forEach((d, i) => {
    aShareByDate[d.date] = { value: d.total_value, x: getX(aShare, i), y: getY(d) };
  });
  const usStockByDate: Record<string, { value: number; x: number; y: number }> = {};
  usStock.forEach((d, i) => {
    usStockByDate[d.date] = { value: d.total_value, x: getX(usStock, i), y: getY(d) };
  });

  // All hover candidates for X-proximity lookup
  const candidates: { svgX: number; date: string }[] = [];
  aShare.forEach((d, i) => candidates.push({ svgX: getX(aShare, i), date: d.date }));
  usStock.forEach((d, i) => candidates.push({ svgX: getX(usStock, i), date: d.date }));

  const getTimeLabels = (arr: DataPoint[]) => {
    const labels: { x: number; label: string }[] = [];
    const step = Math.max(1, Math.floor(arr.length / 6));
    for (let i = 0; i < arr.length; i += step) {
      labels.push({ x: getX(arr, i), label: arr[i].date.slice(5) });
    }
    return labels;
  };

  const timeLabels = getTimeLabels(aShare.length >= 2 ? aShare : usStock);

  const allPoints: { x: number; y: number; date: string; market: string }[] = [];
  aShare.forEach((d, i) => allPoints.push({ x: getX(aShare, i), y: getY(d), date: d.date, market: "A_SHARE" }));
  usStock.forEach((d, i) => allPoints.push({ x: getX(usStock, i), y: getY(d), date: d.date, market: "US_STOCK" }));

  return (
    <div ref={containerRef} className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${w} ${h}`}
        className="w-full h-48 cursor-crosshair"
        onMouseMove={(e) => {
          if (!svgRef.current || !containerRef.current) return;
          const svgRect = svgRef.current.getBoundingClientRect();
          const containerRect = containerRef.current.getBoundingClientRect();
          const mouseX = e.clientX - containerRect.left;
          const mouseY = e.clientY - containerRect.top;
          const svgX = ((e.clientX - svgRect.left) / svgRect.width) * w;

          let nearest: { svgX: number; date: string } | null = null;
          let minDist = Infinity;
          for (const c of candidates) {
            const dist = Math.abs(c.svgX - svgX);
            if (dist < minDist) {
              minDist = dist;
              nearest = c;
            }
          }

          const maxGap = candidates.length > 1
            ? chartW / candidates.length * 1.2
            : chartW * 0.3;
          if (nearest && minDist <= maxGap) {
            setHovered({
              mouseX,
              mouseY,
              containerW: containerRect.width,
              date: nearest.date,
              svgX: nearest.svgX,
              aShare: aShareByDate[nearest.date]?.value,
              usStock: usStockByDate[nearest.date]?.value,
            });
          } else {
            setHovered(null);
          }
        }}
        onMouseLeave={() => setHovered(null)}
      >
        {/* Grid */}
        {[0, 0.25, 0.5, 0.75, 1].map((p) => {
          const y = h - py - p * (h - 2 * py);
          return (
            <g key={p}>
              <line x1={px} y1={y} x2={w - px} y2={y} stroke="rgba(255,255,255,0.06)" />
              <text x={px - 5} y={y + 4} textAnchor="end" className="text-[10px] fill-white/40">
                ¥{fmt(minV + p * range)}
              </text>
            </g>
          );
        })}

        {/* X labels */}
        {timeLabels.map((tl, i) => (
          <text key={i} x={tl.x} y={h - 2} textAnchor="middle" className="text-[10px] fill-white/40">
            {tl.label}
          </text>
        ))}

        {/* Crosshair */}
        {hovered && (
          <line
            x1={hovered.svgX} y1={py} x2={hovered.svgX} y2={h - py}
            stroke="rgba(255,255,255,0.15)" strokeDasharray="4,4"
          />
        )}

        {/* Lines */}
        {aShare.length >= 2 && <polyline points={pts(aShare)} fill="none" stroke="#ef4444" strokeWidth={2} />}
        {usStock.length >= 2 && <polyline points={pts(usStock)} fill="none" stroke="#3b82f6" strokeWidth={2} />}

        {/* Single points */}
        {aShare.length === 1 && <circle cx={getX(aShare, 0)} cy={getY(aShare[0])} r={6} fill="#ef4444" />}
        {usStock.length === 1 && <circle cx={getX(usStock, 0)} cy={getY(usStock[0])} r={6} fill="#3b82f6" />}

        {/* Data dots */}
        {allPoints.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={4}
            fill={p.market === "A_SHARE" ? "#ef4444" : "#3b82f6"}
            opacity={hovered?.date === p.date ? 1 : 0.4}
            className="transition-opacity"
          />
        ))}

        {/* Highlighted dots on hover */}
        {hovered && aShareByDate[hovered.date] && (
          <circle cx={aShareByDate[hovered.date].x} cy={aShareByDate[hovered.date].y}
            r={6} fill="#ef4444" stroke="white" strokeWidth={2} />
        )}
        {hovered && usStockByDate[hovered.date] && (
          <circle cx={usStockByDate[hovered.date].x} cy={usStockByDate[hovered.date].y}
            r={6} fill="#3b82f6" stroke="white" strokeWidth={2} />
        )}
      </svg>

      {/* Tooltip */}
      {hovered && (hovered.aShare != null || hovered.usStock != null) && (
        <div
          className="absolute bg-[#1a1a2e] border border-white/20 rounded-lg px-3 py-2 text-sm shadow-xl z-50 pointer-events-none"
          style={{
            left: hovered.mouseX + 180 > hovered.containerW
              ? hovered.mouseX - 170
              : hovered.mouseX + 15,
            top: Math.max(0, hovered.mouseY - 80),
            minWidth: 160,
          }}
        >
          <div className="text-white/60 text-xs mb-1.5">{hovered.date}</div>
          {hovered.aShare != null && (
            <div className="flex items-center justify-between gap-4 mb-0.5">
              <span className="flex items-center gap-1.5 text-white/80">
                <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />A股
              </span>
              <span className="text-white font-bold">¥{fmt(hovered.aShare)}</span>
            </div>
          )}
          {hovered.usStock != null && (
            <div className="flex items-center justify-between gap-4">
              <span className="flex items-center gap-1.5 text-white/80">
                <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" />美股
              </span>
              <span className="text-white font-bold">¥{fmt(hovered.usStock)}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
