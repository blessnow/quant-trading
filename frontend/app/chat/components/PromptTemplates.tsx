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
          className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-full flex items-center gap-1 transition-colors"
        >
          <span>{p.icon}</span>
          <span>{p.title}</span>
        </button>
      ))}
    </div>
  );
}