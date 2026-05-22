import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";

/**
 * Container for results shown below the form/examples grid. Optional title
 * + counter line, then child content (renders shot tiles, answer text, etc.).
 */
export function ResultsPanel({
  title = "Results",
  counter,
  children,
}: {
  title?: string;
  counter?: string;
  children: ReactNode;
}) {
  return (
    <Card className="p-6">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="text-base font-semibold text-neutral-900">{title}</h2>
        {counter && <span className="text-xs text-neutral-500">{counter}</span>}
      </div>
      {children}
    </Card>
  );
}
