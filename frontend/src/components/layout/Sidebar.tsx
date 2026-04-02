import { useRef } from "react";

type DocumentItem = {
  id: string;
  name: string;
};

type SidebarProps = {
  documents: DocumentItem[];
  activeDoc: string | null;
  uploading: boolean;
  pendingFileName: string | null;
  onUpload: (file: File) => void;
  onNewChat: () => void;
  onSelectDoc: (docId: string) => void;
};

export default function Sidebar({
  documents,
  activeDoc,
  uploading,
  pendingFileName,
  onUpload,
  onNewChat,
  onSelectDoc,
}: SidebarProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  return (
    <aside className="hidden w-72 flex-col border-r border-white/5 bg-neutral-900/95 p-5 md:flex">
      <div className="mb-6">
        <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-cyan-400/80">
          Workspace
        </p>
        <h1 className="mt-2 text-xl font-semibold text-white">Study Copilot</h1>
        <p className="mt-2 text-sm leading-6 text-neutral-400">
          Upload a PDF and keep your active documents one click away.
        </p>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) {
            onUpload(file);
            e.target.value = "";
          }
        }}
        className="hidden"
        disabled={uploading}
      />

      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
        className="group relative mb-4 overflow-hidden rounded-2xl border border-cyan-400/20 bg-gradient-to-br from-cyan-500/20 via-sky-500/10 to-transparent p-4 text-left transition hover:border-cyan-300/40 hover:from-cyan-500/25 hover:via-sky-500/15 disabled:cursor-not-allowed disabled:opacity-70"
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(103,232,249,0.24),transparent_45%)]" />
        <div className="relative flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white/10 text-xl shadow-[0_0_30px_rgba(34,211,238,0.12)]">
            {uploading ? "..." : "PDF"}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-white">
              {uploading ? "Uploading document..." : "Upload PDF"}
            </p>
            <p className="mt-1 text-xs leading-5 text-neutral-300/80">
              {pendingFileName
                ? pendingFileName
                : "Choose a file to build a searchable study workspace."}
            </p>
          </div>
        </div>
      </button>

      {uploading && (
        <p className="mb-4 text-sm text-cyan-200/80">
          Processing pages and preparing search...
        </p>
      )}

      <button
        className="mb-5 rounded-xl border border-white/8 bg-white/5 p-3 text-sm font-medium text-white transition hover:bg-white/10"
        onClick={onNewChat}
      >
        + New Chat
      </button>

      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-neutral-500">
          Documents
        </p>
        <span className="rounded-full border border-white/8 px-2 py-1 text-[11px] text-neutral-400">
          {documents.length}
        </span>
      </div>

      <div className="space-y-2 overflow-y-auto pr-1">
        {documents.map((doc) => (
          <button
            key={doc.id}
            onClick={() => onSelectDoc(doc.id)}
            className={`w-full rounded-xl border p-3 text-left text-sm transition ${
              activeDoc === doc.id
                ? "border-cyan-400/40 bg-cyan-500/15 text-white shadow-[0_0_24px_rgba(34,211,238,0.12)]"
                : "border-white/6 bg-white/[0.03] text-neutral-300 hover:bg-white/[0.06]"
            }`}
          >
            <p className="truncate font-medium">{doc.name}</p>
            <p className="mt-1 text-xs text-neutral-500">
              {activeDoc === doc.id ? "Active document" : "Click to open"}
            </p>
          </button>
        ))}
      </div>
    </aside>
  );
}
