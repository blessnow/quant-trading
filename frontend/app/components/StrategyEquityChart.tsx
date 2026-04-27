"use client";

import { useState, useRef } from "react";

interface DataPoint {
  date: string;
  total_value: number;
  daily_return_pct?: number;
}

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

export function StrategyEquityChart({ data, color = "#4f6ef7" }: { data: DataPoint[]; color?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [hovered, setHovered] = useState<{
    mouseX: number;
    mouseY: number;
    containerW: number;
    date: string;
    svgX: number;
    value: number;
  } | null>(null);

  if (data.length === 0) return null;

  const values = data.map((d) => d.total_value);
  const minV = Math.min(...values) * 0.995;
  const maxV = Math.max(...values) * 1.005;
  const range = maxV - minV || 1;
  const w = 800, h = 240, px = 55, py = 15;
  const chartW = w - 2 * px;

  const getX = (i: number) => {
    if (data.length === 1) return (px + w - px) / 2;
    return px + (i / (data.length - 1)) * (w - 2 * px);
  };

  const getY = (d: DataPoint) =>
    h - py - ((d.total_value - minV) / range) * (h - 2 * py);

  const pts = data.map((d, i) => `${getX(i)},${getY(d)}`).join(" ");

  const byDate: Record<string, { value: number; x: number; y: number }> = {};
  data.forEach((d, i) => {
    byDate[d.date] = { value: d.total_value, x: getX(i), y: getY(d) };
  });

  const candidates = data.map((d, i) => ({ svgX: getX(i), date: d.date }));

  const getTimeLabels = () => {
    const labels: { x: number; label: string }[] = [];
    const step = Math.max(1, Math.floor(data.length / 6));
    for (let i = 0; i < data.length; i += step) {
      labels.push({ x: getX(i), label: data[i].date.slice(5) });
    }
    return labels;
  };

  const timeLabels = getTimeLabels();

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
              value: byDate[nearest.date]?.value || 0,
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
              <line x1={px} y1={y} x2={w - px} y2={y} stroke="#f0f0f0" />
              <text x={px - 5} y={y + 4} textAnchor="end" className="text-[10px] fill-gray-400">
                ¥{fmt(minV + p * range)}
              </text>
            </g>
          );
        })}

        {/* X labels */}
        {timeLabels.map((tl, i) => (
          <text key={i} x={tl.x} y={h - 2} textAnchor="middle" className="text-[10px] fill-gray-400">
            {tl.label}
          </text>
        ))}

        {/* Crosshair */}
        {hovered && (
          <line
            x1={hovered.svgX} y1={py} x2={hovered.svgX} y2={h - py}
            stroke="rgba(0,0,0,0.1)" strokeDasharray="4,4"
          />
        )}

        {/* Line */}
        {data.length >= 2 && <polyline points={pts} fill="none" stroke={color} strokeWidth={2} />}

        {/* Data dots - only show when more than 1 point */}
        {data.length >= 2 && data.map((d, i) => (
          <circle key={i} cx={getX(i)} cy={getY(d)} r={4}
            fill={color}
            opacity={hovered?.date === d.date ? 1 : 0.4}
            className="transition-opacity"
          />
        ))}

        {/* Single point */}
        {data.length === 1 && (
          <circle cx={getX(0)} cy={getY(data[0])} r={6} fill={color} />
        )}

        {/* Highlighted dot on hover */}
        {hovered && byDate[hovered.date] && (
          <circle cx={byDate[hovered.date].x} cy={byDate[hovered.date].y}
            r={6} fill={color} stroke="#1a1a2e" strokeWidth={2} />
        )}
      </svg>

      {/* Tooltip */}
      {hovered && (
        <div
          className="absolute bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm shadow-xl z-50 pointer-events-none"
          style={{
            left: hovered.mouseX + 180 > hovered.containerW
              ? hovered.mouseX - 170
              : hovered.mouseX + 15,
            top: Math.max(0, hovered.mouseY - 60),
            minWidth: 120,
          }}
        >
          <div className="text-gray-400 text-xs mb-1">{hovered.date}</div>
          <div className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-gray-600">
              <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: color }} />净值
            </span>
            <span className="text-[#1a1a2e] font-bold">¥{fmt(hovered.value)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
