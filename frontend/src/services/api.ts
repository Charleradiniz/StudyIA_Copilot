const API_URL = "http://127.0.0.1:8000";

export async function uploadPdf(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_URL}/upload`, {
    method: "POST",
    body: formData,
  });

  return res.json(); // should return doc_id
}

export async function askQuestion(question: string, docId: string) {
  const res = await fetch(`${API_URL}/api/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question,
      doc_id: docId,
    }),
  });

  return res.json();
}
