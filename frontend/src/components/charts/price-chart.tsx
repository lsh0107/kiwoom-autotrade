"use client";

import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { OHLCVData } from "@/types/api";
import { formatKRW } from "@/lib/format";

/** 캔들스틱 커스텀 Bar shape */
function CandleShape(props: {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  payload?: OHLCVData;
  yAxis?: { scale?: (v: number) => number };
}) {
  const { x = 0, width = 0, payload, yAxis } = props;
  if (!payload || !yAxis?.scale) return null;

  const scale = yAxis.scale;
  const openY = scale(payload.open);
  const closeY = scale(payload.close);
  const highY = scale(payload.high);
  const lowY = scale(payload.low);

  const isBull = payload.close >= payload.open;
  const color = isBull ? "#22c55e" : "#ef4444";

  const bodyTop = Math.min(openY, closeY);
  const bodyHeight = Math.max(Math.abs(closeY - openY), 1);
  const centerX = x + width / 2;

  return (
    <g>
      {/* 위 wick */}
      <line
        x1={centerX}
        y1={highY}
        x2={centerX}
        y2={bodyTop}
        stroke={color}
        strokeWidth={1}
      />
      {/* 몸체 */}
      <rect
        x={x + 1}
        y={bodyTop}
        width={Math.max(width - 2, 1)}
        height={bodyHeight}
        fill={color}
        stroke={color}
      />
      {/* 아래 wick */}
      <line
        x1={centerX}
        y1={bodyTop + bodyHeight}
        x2={centerX}
        y2={lowY}
        stroke={color}
        strokeWidth={1}
      />
    </g>
  );
}

/** OHLCV Tooltip */
function OHLCVTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ payload: OHLCVData }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const isBull = d.close >= d.open;

  return (
    <div className="grid min-w-[160px] gap-1.5 rounded-lg border border-border/50 bg-background px-2.5 py-1.5 text-xs shadow-xl">
      <div className="font-medium">{label}</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
        <span className="text-muted-foreground">시가</span>
        <span className="tabular-nums">₩{formatKRW(d.open)}</span>
        <span className="text-muted-foreground">고가</span>
        <span className="tabular-nums text-red-500">₩{formatKRW(d.high)}</span>
        <span className="text-muted-foreground">저가</span>
        <span className="tabular-nums text-blue-500">₩{formatKRW(d.low)}</span>
        <span className="text-muted-foreground">종가</span>
        <span
          className={`tabular-nums font-medium ${isBull ? "text-green-600" : "text-red-600"}`}
        >
          ₩{formatKRW(d.close)}
        </span>
        <span className="text-muted-foreground">거래량</span>
        <span className="tabular-nums">{formatKRW(d.volume)}</span>
      </div>
    </div>
  );
}

interface PriceChartProps {
  data: OHLCVData[];
}

/** 캔들스틱 + 거래량 차트 */
export function PriceChart({ data }: PriceChartProps) {
  if (!data.length) return null;

  const prices = data.flatMap((d) => [d.high, d.low]);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const pricePad = (maxPrice - minPrice) * 0.05;

  return (
    <div className="h-[350px] w-full">
      <ResponsiveContainer width="100%" height="80%">
        <ComposedChart
          data={data}
          margin={{ top: 4, right: 8, left: 8, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-border/40" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10 }}
            tickFormatter={(v: string) => v.slice(5)}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[minPrice - pricePad, maxPrice + pricePad]}
            tick={{ fontSize: 10 }}
            tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}K`}
            width={48}
          />
          <Tooltip content={<OHLCVTooltip />} />
          <Bar
            dataKey="high"
            shape={
              (props: Parameters<typeof CandleShape>[0]) => (
                <CandleShape {...props} />
              )
            }
          >
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.close >= entry.open ? "#22c55e" : "#ef4444"}
              />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>

      {/* 거래량 */}
      <ResponsiveContainer width="100%" height="20%">
        <ComposedChart
          data={data}
          margin={{ top: 0, right: 8, left: 8, bottom: 4 }}
        >
          <XAxis dataKey="date" hide />
          <YAxis
            tick={{ fontSize: 9 }}
            tickFormatter={(v: number) =>
              v >= 1_000_000 ? `${(v / 1_000_000).toFixed(0)}M` : `${(v / 1000).toFixed(0)}K`
            }
            width={48}
          />
          <Bar dataKey="volume" maxBarSize={8}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={
                  entry.close >= entry.open
                    ? "rgba(34,197,94,0.5)"
                    : "rgba(239,68,68,0.5)"
                }
              />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
