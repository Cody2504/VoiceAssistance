import axios from "axios";

import { ROUTES } from "@/constants/routes";

export interface IndexSummary {
  id: string;
  user_id: string;
  title: string | null;
  description: string | null;
  language: string;
  created_at: string;
  video_count: number;
  total_duration_s: number | null;
}

export interface IndexVideoEntry {
  video_id: string;
  position: number;
  original_filename: string;
  duration_s: number | null;
  status: string;
}

export async function listIndexes(): Promise<IndexSummary[]> {
  const r = await axios.get(ROUTES.INDEXES);
  return r.data?.data ?? [];
}

export async function getIndex(id: string): Promise<IndexSummary> {
  const r = await axios.get(ROUTES.INDEX(id));
  return r.data?.data;
}

export async function createIndex(payload: {
  title?: string;
  description?: string;
  language?: string;
}): Promise<IndexSummary> {
  const r = await axios.post(ROUTES.INDEXES, payload);
  return r.data?.data;
}

export async function deleteIndex(id: string): Promise<void> {
  await axios.delete(ROUTES.INDEX(id));
}

export async function listIndexVideos(id: string): Promise<IndexVideoEntry[]> {
  const r = await axios.get(ROUTES.INDEX_VIDEOS(id));
  return r.data?.data ?? [];
}

export async function addVideoToIndex(
  id: string,
  videoId: string,
  position?: number,
): Promise<IndexVideoEntry> {
  const r = await axios.post(ROUTES.INDEX_VIDEOS(id), {
    video_id: videoId,
    position: position ?? null,
  });
  return r.data?.data;
}

export async function removeVideoFromIndex(id: string, videoId: string): Promise<void> {
  await axios.delete(ROUTES.INDEX_VIDEO(id, videoId));
}

export interface IndexShot {
  video_id: string;
  original_filename: string;
  video_duration_s: number | null;
  idx: number;
  t_start: number;
  t_end: number;
  asr_text: string;
  ocr_text?: string;
  audio_tags?: Array<{ label: string; score: number }>;
  score: number;
}

export interface IndexSearchResponse {
  query: string;
  index_id: string;
  group_by: "clip" | "video";
  shots: IndexShot[];
}

export async function searchInIndex(
  id: string,
  params: {
    query: string;
    video_ids?: string[];
    top_n?: number;
    group_by?: "clip" | "video";
  },
): Promise<IndexSearchResponse> {
  const r = await axios.post(ROUTES.INDEX_SEARCH(id), {
    query: params.query,
    video_ids: params.video_ids ?? [],
    top_n: params.top_n ?? 10,
    group_by: params.group_by ?? "video",
  });
  return r.data?.data;
}

// ---------------------------------------------------------------------------
// Phase 2a — Knowledge-graph endpoints (separate from text retrieval).
// ---------------------------------------------------------------------------

export interface Concept {
  entity_id: string;
  canonical_name: string;
  entity_type: string | null;
  description: string | null;
  score: number;
  mention_count: number;
  video_count: number;
}

export interface ConceptSearchResponse {
  query: string;
  index_id: string;
  concepts: Concept[];
  kg_available: boolean;
}

export async function searchConcepts(
  id: string,
  params: { query: string; top_k?: number; entity_types?: string[] },
): Promise<ConceptSearchResponse> {
  const r = await axios.post(ROUTES.INDEX_CONCEPTS_SEARCH(id), {
    query: params.query,
    top_k: params.top_k ?? 10,
    entity_types: params.entity_types ?? null,
  });
  return r.data?.data;
}

export interface ConceptMention {
  video_id: string;
  video_title: string;
  video_position: number;
  segment_idx: number;
  t_start: number | null;
  t_end: number | null;
  transcript: string;
  caption: string;
  weight: number;
}

export async function listEntityMentions(
  indexId: string,
  entityId: string,
  params?: { video_ids?: string[]; limit?: number },
): Promise<{ mentions: ConceptMention[]; index_id: string; entity_id: string }> {
  const queryParams: Record<string, string | number> = {};
  if (params?.video_ids?.length) queryParams.video_ids = params.video_ids.join(",");
  if (params?.limit !== undefined) queryParams.limit = params.limit;
  const r = await axios.get(ROUTES.INDEX_ENTITY_MENTIONS(indexId, entityId), {
    params: queryParams,
  });
  return r.data?.data;
}

export interface RelatedConcept {
  entity_id: string;
  canonical_name: string;
  entity_type: string | null;
  description: string | null;
  relation: string;
  relation_description: string | null;
  weight: number;
  direction: "outgoing" | "incoming";
}

export async function listEntityRelated(
  indexId: string,
  entityId: string,
  params?: { direction?: "both" | "outgoing" | "incoming"; top_k?: number },
): Promise<{ related: RelatedConcept[]; index_id: string; entity_id: string }> {
  const r = await axios.get(ROUTES.INDEX_ENTITY_RELATED(indexId, entityId), {
    params: {
      direction: params?.direction ?? "both",
      top_k: params?.top_k ?? 20,
    },
  });
  return r.data?.data;
}
