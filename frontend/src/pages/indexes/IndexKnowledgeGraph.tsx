import { useEffect, useRef } from "react";
import { Link, useParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ArrowLeft, Loader2, Waypoints } from "lucide-react";
import { DataSet } from "vis-data";
import { Network } from "vis-network";
import "vis-network/styles/vis-network.css";

import { getIndexGraph } from "@/apis/indexes.api";

// The 8 entity types the KG extractor emits, each with a distinct node colour.
const ENTITY_TYPES = [
  "concept",
  "method",
  "person",
  "organization",
  "tool",
  "event",
  "location",
  "object",
] as const;

const TYPE_COLORS: Record<string, string> = {
  concept: "#4C9AFF",
  method: "#57D9A3",
  person: "#FF8B00",
  organization: "#FFC400",
  tool: "#998DD9",
  event: "#FF5630",
  location: "#36B37E",
  object: "#00B8D9",
};
const DEFAULT_COLOR = "#A5ADBA";

export default function IndexKnowledgeGraph() {
  const { t } = useTranslation();
  const { indexId } = useParams<{ indexId: string }>();
  const containerRef = useRef<HTMLDivElement | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["index-graph", indexId],
    queryFn: () => getIndexGraph(indexId as string),
    enabled: !!indexId,
  });

  const hasGraph = !!data && data.kg_available && data.nodes.length > 0;

  useEffect(() => {
    if (!hasGraph || !data || !containerRef.current) return;

    const nodes = new DataSet(
      data.nodes.map((n) => ({
        id: n.id,
        label: n.label,
        title: n.description ? `${n.type ?? "entity"} — ${n.description}` : n.type ?? "entity",
        color: TYPE_COLORS[n.type ?? ""] ?? DEFAULT_COLOR,
        value: n.mention_count + 1,
      })),
    );
    const edges = new DataSet(
      data.edges.map((e, i) => ({
        id: i,
        from: e.source,
        to: e.target,
        label: e.relation,
        title: e.description ?? e.relation,
        value: e.weight,
        arrows: "to",
      })),
    );

    const network = new Network(
      containerRef.current,
      { nodes, edges },
      {
        nodes: {
          shape: "dot",
          font: { color: "#1a1a1a", size: 14, face: "Inter, system-ui, sans-serif" },
          borderWidth: 1,
          scaling: { min: 8, max: 42 },
        },
        edges: {
          color: { color: "#cbd5e1", highlight: "#475569", hover: "#94a3b8" },
          font: {
            size: 10,
            color: "#64748b",
            strokeWidth: 3,
            strokeColor: "#ffffff",
            align: "middle",
          },
          smooth: { enabled: true, type: "continuous", roundness: 0.5 },
          scaling: { min: 1, max: 6 },
          arrows: { to: { enabled: true, scaleFactor: 0.6 } },
        },
        physics: {
          solver: "forceAtlas2Based",
          forceAtlas2Based: { gravitationalConstant: -45, springLength: 120 },
          stabilization: { iterations: 180 },
        },
        interaction: { hover: true, tooltipDelay: 120, navigationButtons: true, keyboard: false },
      },
    );

    return () => network.destroy();
  }, [hasGraph, data]);

  return (
    <div className="mx-auto max-w-[1180px] px-8 pt-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            to={`/indexes/${indexId}`}
            aria-label={t("console.index_detail.kg_back")}
            className="grid h-9 w-9 place-items-center rounded-md text-[var(--color-gravel)] transition hover:bg-[var(--color-powder)]"
          >
            <ArrowLeft size={18} />
          </Link>
          <h1 className="inline-flex items-center gap-2 text-[22px] font-medium tracking-[-0.3px] text-[var(--color-obsidian)]">
            <Waypoints size={20} />
            {t("console.index_detail.kg_page_title")}
          </h1>
        </div>
        {data?.truncated && (
          <span className="rounded-full bg-amber-50 px-3 py-1 text-[12px] text-amber-700">
            {t("console.index_detail.kg_truncated", {
              shown: data.nodes.length,
              total: data.total_nodes,
            })}
          </span>
        )}
      </div>

      {hasGraph && (
        <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12px] text-[var(--color-gravel)]">
          <span className="font-medium text-[var(--color-obsidian)]">
            {t("console.index_detail.kg_legend")}:
          </span>
          {ENTITY_TYPES.map((ty) => (
            <span key={ty} className="inline-flex items-center gap-1.5">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: TYPE_COLORS[ty] }}
              />
              {t(`console.index_detail.kg_types.${ty}`)}
            </span>
          ))}
        </div>
      )}

      <div
        className="relative rounded-2xl border border-[var(--color-chalk)] bg-white"
        style={{ height: "calc(100vh - 230px)" }}
      >
        {isLoading && (
          <div className="absolute inset-0 grid place-items-center text-[14px] text-[var(--color-gravel)]">
            <span className="inline-flex items-center gap-2">
              <Loader2 size={18} className="animate-spin" />
              {t("console.index_detail.kg_loading")}
            </span>
          </div>
        )}
        {isError && (
          <div className="absolute inset-0 grid place-items-center">
            <div className="flex flex-col items-center gap-3 text-[14px] text-[var(--color-gravel)]">
              {t("console.index_detail.kg_error")}
              <button
                onClick={() => refetch()}
                className="rounded-[12px] border border-[var(--color-chalk)] px-4 py-1.5 text-[13px] text-[var(--color-obsidian)] transition hover:bg-[var(--color-powder)]"
              >
                {t("console.index_detail.kg_retry")}
              </button>
            </div>
          </div>
        )}
        {!isLoading && !isError && !hasGraph && (
          <div className="absolute inset-0 grid place-items-center px-8 text-center text-[14px] text-[var(--color-gravel)]">
            {t("console.index_detail.kg_empty")}
          </div>
        )}
        <div ref={containerRef} className="h-full w-full" />
      </div>
    </div>
  );
}
