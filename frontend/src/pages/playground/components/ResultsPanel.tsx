import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Card } from "@/components/ui/card";

/**
 * Container for results shown below the form/examples grid. Optional title
 * + counter line, then child content (renders shot tiles, answer text, etc.).
 */
export function ResultsPanel({
  title,
  counter,
  children,
}: {
  title?: string;
  counter?: string;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const resolvedTitle = title ?? t("pgkit.results.title");
  return (
    <Card className="p-6">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="text-base font-semibold text-neutral-900">{resolvedTitle}</h2>
        {counter && <span className="text-xs text-neutral-500">{counter}</span>}
      </div>
      {children}
    </Card>
  );
}
