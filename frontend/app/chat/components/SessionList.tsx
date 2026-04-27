"use client";

interface Session {
  id: number;
  strategy_id: string;
  title: string;
  updated_at: string;
}

interface Props {
  sessions: Session[] | undefined;
  current: Session | null;
  onSelect: (s: Session) => void;
  onDelete: (id: number) => void;
}

export default function SessionList({ sessions = [], current, onSelect, onDelete }: Props) {
  return (
    <div className="flex-1 overflow-y-auto">
      {!sessions || sessions.length === 0 ? (
        <div className="p-4 text-center text-white/40 text-sm">
          暂无对话记录
        </div>
      ) : (
        <ul className="divide-y divide-white/5">
          {sessions.map((s) => (
            <li
              key={s.id}
              className={`group p-3 cursor-pointer hover:bg-white/5 transition-colors ${
                current?.id === s.id ? "bg-white/10" : ""
              }`}
              onClick={() => onSelect(s)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{s.title}</p>
                  <p className="text-xs text-white/40 mt-1">
                    {new Date(s.updated_at).toLocaleDateString()}
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(s.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 rounded text-red-400 transition-opacity"
                >
                  ×
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
