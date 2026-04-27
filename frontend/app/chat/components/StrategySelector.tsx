"use client";

interface Strategy {
  id: string;
  name: string;
  avatar: string;
  color: string;
  description: string;
  prompts: { title: string; content: string; icon: string }[];
}

interface Props {
  strategies: Strategy[] | undefined;
  current: Strategy | null;
  onSelect: (s: Strategy) => void;
}

export default function StrategySelector({ strategies = [], current, onSelect }: Props) {
  return (
    <div className="flex items-center gap-2">
      {strategies && strategies.map((s) => (
        <button
          key={s.id}
          onClick={() => onSelect(s)}
          className={`px-4 py-2 rounded-lg flex items-center gap-2 transition-all ${
            current?.id === s.id
              ? "ring-2 ring-offset-2 ring-offset-[#0a0f1a]"
              : "bg-white/5 hover:bg-white/10 border border-white/10"
          }`}
          style={{
            backgroundColor: current?.id === s.id ? `${s.color}30` : undefined,
            "--tw-ring-color": current?.id === s.id ? s.color : undefined,
          } as React.CSSProperties}
        >
          <span className="text-xl">{s.avatar}</span>
          <span className={`font-medium ${current?.id === s.id ? "text-white" : "text-white/70"}`}>
            {s.name}
          </span>
        </button>
      ))}
    </div>
  );
}
