import { Outlet } from "react-router";

import { NavBar } from "@/components/landing/NavBar";

export default function PublicLayout() {
  return (
    <div className="min-h-screen bg-[var(--color-eggshell)] text-[var(--color-obsidian)] app-ground">
      <NavBar />
      <Outlet />
    </div>
  );
}
