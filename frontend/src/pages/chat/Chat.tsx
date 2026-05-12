import { ChatThread } from "@/components/chat/ChatThread";

export default function Chat() {
  return (
    <div className="mx-auto h-full max-w-3xl px-6 py-6">
      <header className="mb-4">
        <h1 className="text-base font-semibold">Jockey</h1>
        <p className="text-xs text-neutral-500">your video assistant</p>
      </header>
      <ChatThread />
    </div>
  );
}
