"use client";

interface Props {
  toolCall: {
    name: string;
    args: Record<string, unknown>;
    result?: string;
  };
}

const TOOL_NAMES: Record<string, string> = {
  search_web: "搜索网络",
  get_market_data: "获取市场数据",
  get_stock_info: "查询股票信息",
  get_positions: "获取持仓",
  get_stock_fundamentals: "获取基本面数据",
  get_pb_ratio: "获取估值数据",
  get_commodity_prices: "获取商品价格",
};

export default function ToolCallDisplay({ toolCall }: Props) {
  const displayName = TOOL_NAMES[toolCall.name] || toolCall.name || "工具";
  const args =
    toolCall.args && typeof toolCall.args === "object" && !Array.isArray(toolCall.args)
      ? (toolCall.args as Record<string, unknown>)
      : {};

  return (
    <div className="bg-white/5 border border-white/10 rounded-lg p-3 text-sm">
      <div className="flex items-center gap-2 text-white/70">
        <span className="text-lg">🔧</span>
        <span className="font-medium">{displayName}</span>
      </div>

      {/* 参数 */}
      {Object.keys(args).length > 0 && (
        <div className="mt-2 text-xs text-white/50">
          {Object.entries(args).map(([k, v]) => (
            <span key={k} className="mr-3">
              {k}: <code className="bg-white/10 px-1.5 py-0.5 rounded text-white/70">{String(v)}</code>
            </span>
          ))}
        </div>
      )}

      {/* 结果 */}
      {toolCall.result && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-white/40 hover:text-white/60 transition-colors">
            查看结果
          </summary>
          <pre className="mt-2 text-xs bg-white/5 border border-white/10 rounded p-2 overflow-x-auto max-h-40 text-white/70">
            {toolCall.result.slice(0, 500)}
            {toolCall.result.length > 500 && "..."}
          </pre>
        </details>
      )}
    </div>
  );
}
