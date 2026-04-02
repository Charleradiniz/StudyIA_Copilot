import { useState } from "react";

import { uploadPdf } from "../../services/api";

type SidebarProps = {
  setDocId: (docId: string) => void;
};

export default function Sidebar({ setDocId }: SidebarProps) {
  const [loading, setLoading] = useState(false);
  const [fileName, setFileName] = useState("");

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setLoading(true);
      setFileName(file.name);

      const data = await uploadPdf(file);

      console.log("UPLOAD:", data);

      setDocId(data.doc_id);

      localStorage.setItem("doc_id", data.doc_id);
      localStorage.setItem("doc_name", file.name);

    } catch (err) {
      console.error("Upload error:", err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-64 h-full border-r p-4">
      <h2 className="text-lg font-bold mb-4">Documents</h2>

      <input
        type="file"
        accept="application/pdf"
        onChange={handleFileUpload}
      />

      {fileName && (
        <p className="text-xs text-gray-500 mt-2">
          Current: {fileName}
        </p>
      )}

      {loading && (
        <p className="text-sm text-gray-500 mt-2">
          Processing PDF...
        </p>
      )}
    </div>
  );
}
