"use client";

interface Props {
  prompts: { title: string; content: string; icon: string }[] | undefined;
  onSelect: (content: string) => void;
}

export default function PromptTemplates({ prompts = [], onSelect }: Props) {
  return (
    <div className="flex items-center gap-2">
      {prompts && prompts.map((p, i) => (
        <button
          key={i}
          onClick={() => onSelect(p.content)}
          className="px-3 py-1.5 text-sm bg-white/5 hover:bg-white/10 border border-white/10 rounded-full flex items-center gap-1.5 transition-colors text-white/70 hover:text-white"
        >
          <span>{p.icon}</span>
          <span>{p.title}</span>
        </button>
      ))}
    </div>
  );
}
