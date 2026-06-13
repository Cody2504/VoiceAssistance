import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { ChevronDown, MoreHorizontal, Trash2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { deleteConversation } from "@/apis/chat.api";
import { qk, useConversationsQuery } from "@/apis/queries";
import { useAuth } from "@/contexts/AuthContext";
import { useSidebar } from "@/contexts/SidebarContext";
import { cn } from "@/lib/utils";

/**
 * ChatGPT-style recents list under the "New chat" button. Rows link to
 * /chat/:id; a hover ⋯ menu offers Delete. Hidden entirely when the sidebar
 * is collapsed (the + icon button is the only chat affordance then).
 */
export function SidebarChats() {
  const { collapsed } = useSidebar();
  const { t } = useTranslation();
  const { user } = useAuth();
  const { data: conversations, isError } = useConversationsQuery();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [menuFor, setMenuFor] = useState<string | null>(null);
  // Collapsible section — remembered across sessions so users who don't chat
  // much can keep the sidebar compact.
  const [open, setOpen] = useState(() => localStorage.getItem("sidebar-chats-open") !== "0");
  const menuRef = useRef<HTMLDivElement | null>(null);

  function toggleOpen() {
    setOpen((v) => {
      localStorage.setItem("sidebar-chats-open", v ? "0" : "1");
      return !v;
    });
  }

  // Close the row menu on outside click / Escape.
  useEffect(() => {
    if (!menuFor) return;
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuFor(null);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuFor(null);
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuFor]);

  if (collapsed) return null;

  const activeId = pathname.startsWith("/chat/") ? pathname.slice("/chat/".length) : null;

  async function onDelete(id: string) {
    setMenuFor(null);
    if (!window.confirm(t("chat.sidebar.delete_confirm"))) return;
    await deleteConversation(id);
    await queryClient.invalidateQueries({ queryKey: qk.conversations(user?.id) });
    if (id === activeId) navigate("/workspace");
  }

  return (
    <div className="mb-6 min-h-0">
      <button
        type="button"
        onClick={toggleOpen}
        aria-expanded={open}
        className="flex w-full cursor-pointer items-center justify-between rounded-lg px-1 pb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-slate)] transition hover:text-[var(--color-obsidian)]"
      >
        {t("chat.sidebar.chats_heading")}
        <ChevronDown
          size={13}
          className={cn("transition-transform duration-200", !open && "-rotate-90")}
        />
      </button>
      {open && isError && (
        <p className="px-1 text-[12px] text-[var(--color-gravel)]">{t("chat.sidebar.load_failed")}</p>
      )}
      {open && (
      <div className="max-h-[30vh] space-y-0.5 overflow-y-auto">
        {(conversations ?? []).map((c) => (
          <div key={c.id} className="group relative">
            <Link
              to={`/chat/${c.id}`}
              className={cn(
                "block truncate rounded-lg px-2 py-1.5 pr-8 text-[13px] transition-colors",
                c.id === activeId
                  ? "bg-[var(--color-chalk)] font-medium text-[var(--color-obsidian)]"
                  : "text-[var(--color-obsidian)]/80 hover:bg-[var(--color-powder)]"
              )}
            >
              {c.title || t("chat.sidebar.untitled")}
            </Link>
            <button
              type="button"
              aria-label={t("chat.sidebar.delete")}
              onClick={() => setMenuFor(menuFor === c.id ? null : c.id)}
              className="absolute right-1 top-1/2 hidden h-6 w-6 -translate-y-1/2 cursor-pointer place-items-center rounded-md text-[var(--color-gravel)] hover:bg-[var(--color-chalk)] hover:text-[var(--color-obsidian)] group-hover:grid"
            >
              <MoreHorizontal size={14} />
            </button>
            {menuFor === c.id && (
              <div
                ref={menuRef}
                className="absolute right-0 top-8 z-50 w-32 rounded-xl border border-[var(--color-chalk)] bg-white p-1 shadow-[0_20px_50px_-25px_rgba(0,0,0,0.4)]"
              >
                <button
                  type="button"
                  onClick={() => void onDelete(c.id)}
                  className="flex w-full cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-[13px] text-red-600 transition hover:bg-red-50"
                >
                  <Trash2 size={13} />
                  {t("chat.sidebar.delete")}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
      )}
    </div>
  );
}
