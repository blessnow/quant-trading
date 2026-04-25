"use client";

interface Strategy {
  id: string;
  name: string;
  avatar: string;
  color: string;
  description: string;
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
              ? `bg-opacity-20 ring-2`
              : "bg-gray-100 hover:bg-gray-200"
          }`}
          style={{
            backgroundColor: current?.id === s.id ? `${s.color}20` : undefined,
            ringColor: current?.id === s.id ? s.color : undefined,
          }}
        >
          <span className="text-xl">{s.avatar}</span>
          <span className={`font-medium ${current?.id === s.id ? "" : "text-gray-700"}`}>
            {s.name}
          </span>
        </button>
      ))}
    </div>
  );
}