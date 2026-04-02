import { useState, useEffect, useRef } from "react";
import { askQuestion } from "./services/api";
import PdfModal from "./components/PdfModal";
import Sidebar from "./components/layout/Sidebar";

type Source = {
  id: number;
  text: string;
  score?: number;
  doc_id?: string;
  chunk_id?: number;
  page?: number;
  bbox?: number[];
  line_boxes?: number[][];
  pdf_width?: number;
  pdf_height?: number;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
};

const API_URL = "http://127.0.0.1:8000";

export default function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hello! Send me a document and ask a question.",
    },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const [documents, setDocuments] = useState<
    { id: string; name: string }[]
  >([]);
  const [pendingFileName, setPendingFileName] = useState<string | null>(null);

  const [activeDoc, setActiveDoc] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const [pdfOpen, setPdfOpen] = useState(false);
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);
  const [pdfFocusToken, setPdfFocusToken] = useState(0);

  // Modal document id used by the PDF viewer.
  const [modalDocId, setModalDocId] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // =========================
  // DEBUG 
  // =========================
  useEffect(() => {
    console.log("ACTIVE DOC:", activeDoc);
  }, [activeDoc]);

  useEffect(() => {
    console.log("PDF OPEN:", pdfOpen);
  }, [pdfOpen]);

  // =========================
  // PDF URL
  // =========================
  const pdfUrl = modalDocId
    ? `${API_URL}/api/pdf/${modalDocId}`
    : "";

  useEffect(() => {
    console.log("PDF URL:", pdfUrl);
  }, [pdfUrl]);

  // =========================
  // UPLOAD PDF
  // =========================
  const handleFileUpload = async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);

    setPendingFileName(file.name);
    setUploading(true);

    try {
      const res = await fetch(`${API_URL}/api/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      const id = data.doc_id;

      console.log("UPLOAD RESPONSE:", data);

      if (!id) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "Error: backend did not return a valid doc_id.",
          },
        ]);
        return;
      }

      setDocuments((prev) => [
        ...prev,
        { id, name: data.name || file.name },
      ]);

      setActiveDoc(id);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Document "${data.name || file.name}" uploaded successfully.`,
        },
      ]);
    } catch (err) {
      console.error(err);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Error uploading the document.",
        },
      ]);
    } finally {
      setUploading(false);
    }
  };

  // =========================
  // SEND QUESTION
  // =========================
  const handleSend = async () => {
    if (!input.trim() || loading) return;

    if (!activeDoc) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Upload a document before asking questions.",
        },
      ]);
      return;
    }

    const question = input;

    setInput("");
    setLoading(true);

    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      { role: "assistant", content: "...", sources: [] },
    ]);

    try {
      const data = await askQuestion(question, activeDoc);

      console.log("ASK RESPONSE:", data);

      const fullText = data.answer || "No response from the server.";
      const sources = data.sources || [];

      let i = 0;

      const interval = setInterval(() => {
        i++;

        setMessages((prev) => {
          const updated = [...prev];

          updated[updated.length - 1] = {
            role: "assistant",
            content: fullText.slice(0, i),
            sources: i >= fullText.length ? sources : [],
          };

          return updated;
        });

        if (i >= fullText.length) {
          clearInterval(interval);
        }
      }, 15);
    } catch (error) {
      console.error(error);

      setMessages((prev) => {
        const updated = [...prev];

        updated[updated.length - 1] = {
          role: "assistant",
          content: "Error fetching the answer.",
        };

        return updated;
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-neutral-900 text-white">
      <Sidebar
        documents={documents}
        activeDoc={activeDoc}
        uploading={uploading}
        pendingFileName={pendingFileName}
        onUpload={handleFileUpload}
        onNewChat={() => {
          setMessages([
            {
              role: "assistant",
              content: "New chat started. Upload a document.",
            },
          ]);
          setActiveDoc(null);
        }}
        onSelectDoc={(docId) => {
          console.log("DOC CLICK:", docId);
          setActiveDoc(docId);
        }}
      />

      {/* CHAT */}
      <main className="flex-1 flex flex-col">
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((msg, index) => (
            <div
              key={index}
              className={`max-w-2xl ${
                msg.role === "user" ? "ml-auto text-right" : ""
              }`}
            >
              <div
                className={`p-3 rounded-lg ${
                  msg.role === "user"
                    ? "bg-blue-600"
                    : "bg-neutral-700"
                }`}
              >
                {msg.content}

                {/* SOURCES */}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-3 text-sm text-gray-300 space-y-1">
                    <p className="font-semibold">Sources:</p>

                    {msg.sources.map((s) => (
                      <div
                        key={s.id}
                        onClick={() => {
                          console.log("SOURCE CLICKED:", s);

                          setSelectedSource({
                            ...s,
                            bbox: s.bbox ? [...s.bbox] : undefined,
                            line_boxes: s.line_boxes?.map((box) => [...box]) ?? undefined,
                          });
                          setModalDocId(s.doc_id || activeDoc);
                          setPdfFocusToken((current) => current + 1);
                          setPdfOpen(true);
                        }}
                        className="bg-neutral-800 p-2 rounded text-xs cursor-pointer hover:bg-neutral-700 transition"
                      >
                        [{s.id}]{" "}
                        {s.score && `(${s.score.toFixed(2)})`}{" "}
                        {s.text}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          <div ref={chatEndRef} />
        </div>

        {/* INPUT */}
        <div className="p-4 border-t border-neutral-700">
          <div className="flex gap-2 max-w-2xl mx-auto">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                activeDoc
                  ? "Ask something about the document..."
                  : "Upload a PDF first..."
              }
              className="flex-1 p-3 rounded-lg bg-neutral-800 border border-neutral-700 focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSend();
              }}
              disabled={loading}
            />

            <button
              onClick={handleSend}
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-500 px-4 rounded-lg disabled:opacity-50"
            >
              {loading ? "..." : "Send"}
            </button>
          </div>
        </div>
      </main>

      {/* MODAL PDF */}
      <PdfModal
        open={pdfOpen}
        onClose={() => {
          console.log("MODAL CLOSED");
          setPdfOpen(false);
        }}
        fileUrl={pdfUrl}
        highlight={selectedSource}
        focusToken={pdfFocusToken}
      />
    </div>
  );
}
