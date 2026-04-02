type Props = {
  role: "user" | "assistant";
  content: string;
};

export default function Message({ role, content }: Props) {
  return (
    <div className={`max-w-2xl ${role === "user" ? "ml-auto text-right" : ""}`}>
      <div
        className={`p-3 rounded-lg ${
          role === "user" ? "bg-blue-600" : "bg-neutral-700"
        }`}
      >
        {content}
      </div>
    </div>
  );
}