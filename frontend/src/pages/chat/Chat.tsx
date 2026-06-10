import { useTranslation } from "react-i18next";
import { ChatThread } from "@/components/chat/ChatThread";

export default function Chat() {
  const { t } = useTranslation();
  return (
    <div className="mx-auto h-full max-w-3xl px-6 py-6">
      <header className="mb-4">
        <h1 className="text-base font-semibold">{t("chat.thread.title")}</h1>
        <p className="text-xs text-neutral-500">{t("chat.thread.subtitle")}</p>
      </header>
      <ChatThread />
    </div>
  );
}
