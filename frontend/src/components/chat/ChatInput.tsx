type Props = {
  input: string;
  setInput: (v: string) => void;
  onSend: () => void;
};

export default function ChatInput({ input, setInput, onSend }: Props) {
  return (
    <div className="p-4 border-t border-neutral-700">
      <div className="flex gap-2 max-w-2xl mx-auto">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask something..."
          className="flex-1 p-3 rounded-lg bg-neutral-800 border border-neutral-700"
        />
        <button
          onClick={onSend}
          className="bg-blue-600 hover:bg-blue-500 px-4 rounded-lg"
        >
          Send
        </button>
      </div>
    </div>
  );
}
