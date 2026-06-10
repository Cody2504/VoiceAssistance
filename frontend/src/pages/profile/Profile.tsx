import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Card } from "@/components/ui/card";
import { getMyUsage, type UsageDay } from "@/apis/usage.api";

export default function Profile() {
  const { t } = useTranslation();
  const [days, setDays] = useState<UsageDay[]>([]);

  useEffect(() => {
    getMyUsage().then((u) => setDays(u.days)).catch(() => setDays([]));
  }, []);

  const total = days.reduce((acc, d) => ({
    prompt: acc.prompt + d.prompt_tokens,
    completion: acc.completion + d.completion_tokens,
    cost: acc.cost + d.cost_usd,
  }), { prompt: 0, completion: 0, cost: 0 });

  const max = Math.max(...days.map((d) => d.prompt_tokens + d.completion_tokens), 1);

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-6 text-xl font-semibold">{t("settings.profile.title")}</h1>

      <div className="mb-6 grid grid-cols-3 gap-3">
        <Card>
          <p className="text-xs text-slate-500">{t("settings.profile.prompt_tokens")}</p>
          <p className="text-2xl font-semibold">{total.prompt.toLocaleString()}</p>
        </Card>
        <Card>
          <p className="text-xs text-slate-500">{t("settings.profile.completion_tokens")}</p>
          <p className="text-2xl font-semibold">{total.completion.toLocaleString()}</p>
        </Card>
        <Card>
          <p className="text-xs text-slate-500">{t("settings.profile.cost")}</p>
          <p className="text-2xl font-semibold">${total.cost.toFixed(2)}</p>
        </Card>
      </div>

      <Card>
        <h2 className="mb-3 text-sm font-medium">{t("settings.profile.daily_usage")}</h2>
        <div className="space-y-1">
          {days.length === 0 && <p className="text-xs text-slate-500">{t("settings.profile.no_usage")}</p>}
          {days.map((d) => {
            const total = d.prompt_tokens + d.completion_tokens;
            const pct = (total / max) * 100;
            return (
              <div key={d.day} className="flex items-center gap-3 text-xs">
                <span className="w-24 font-mono text-slate-500">{d.day.slice(0, 10)}</span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/5">
                  <div className="h-full bg-indigo-400" style={{ width: `${pct}%` }} />
                </div>
                <span className="w-20 text-right text-slate-400">{total.toLocaleString()}</span>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
