import axios from "axios";
import { ROUTES } from "@/constants/routes";

export type VideoModality = "video_audio" | "video_only" | "audio_only";

export interface VideoSummary {
  id: string;
  user_id: string;
  original_filename: string;
  duration_s: number | null;
  size_bytes: number | null;
  status: "stored" | "queued" | "processing" | "ready" | "error";
  shot_count: number | null;
  error: string | null;
  created_at: string;
  modality?: VideoModality | null;
  has_video?: boolean | null;
  has_audio?: boolean | null;
  global_summary?: string | null;
}

/** Helper used by playground tiles to decide whether they should run on a given video. */
export function tileSupportsModality(
  tile: "search" | "analyze" | "ground" | "highlights" | "segment" | "sounds" | "recommend" | "moderate",
  modality?: VideoModality | null,
): boolean {
  // If we don't know the modality yet (older videos, mid-migration), default to true.
  if (!modality) return true;
  if (modality === "audio_only") {
    return tile === "analyze" || tile === "ground" || tile === "highlights" || tile === "sounds";
  }
  if (modality === "video_only") {
    // No audio → sounds and audio-tagging features have nothing to chew on.
    return tile !== "sounds";
  }
  return true; // video_audio supports everything
}

export async function listVideos(): Promise<VideoSummary[]> {
  const r = await axios.get(ROUTES.VIDEOS);
  return r.data?.data ?? [];
}

export async function getVideo(id: string): Promise<VideoSummary> {
  const r = await axios.get(ROUTES.VIDEO(id));
  return r.data?.data;
}

export async function deleteVideo(id: string): Promise<void> {
  await axios.delete(ROUTES.VIDEO(id));
}

export async function getStreamUrl(id: string): Promise<string> {
  const r = await axios.get(ROUTES.VIDEO_STREAM(id));
  return r.data?.data?.url;
}

export async function getThumbUrl(id: string, shotIdx: number = 0): Promise<string> {
  const r = await axios.get(ROUTES.VIDEO_THUMB(id, shotIdx));
  return r.data?.data?.url;
}

/** Poster thumbnail generated at upload (falls back to shot 0 server-side for
 *  videos ingested before posters existed). 404s until a frame exists. */
export async function getPosterUrl(id: string): Promise<string> {
  const r = await axios.get(ROUTES.VIDEO_POSTER(id));
  return r.data?.data?.url;
}

export async function uploadVideo(file: File, onProgress?: (pct: number) => void): Promise<VideoSummary> {
  const form = new FormData();
  form.append("file", file);
  const r = await axios.post(ROUTES.VIDEOS, form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (e.total) onProgress?.(Math.round((e.loaded / e.total) * 100));
    },
  });
  return r.data?.data;
}

export interface ShotResult {
  idx: number;
  t_start: number;
  t_end: number;
  relevance?: number;
  asr_text?: string;
  score?: number;
}

export interface Span { t_start: number; t_end: number; score: number; }

/**
 * New Ground response shape — `moments` carries sub-second (start, end, score)
 * spans from InternVideo2 features + a trained SG-DETR head (with CG-DETR /
 * QD-DETR-CLAP as the fallback path for audio-only inputs).
 * `shots`/`spans` are retained as optional for backwards compatibility with
 * the legacy QD-DETR backend during migration.
 */
export interface GroundMoment { t_start: number; t_end: number; score: number; }

export interface GroundResponse {
  video_id: string;
  query: string;
  moments?: GroundMoment[];
  modality_used?: "visual" | "audio";
  candidate_windows?: number;
  // Legacy fields, kept for the QD-DETR fallback path.
  shots?: ShotResult[];
  spans?: Span[];
}

export async function groundVideo(id: string, query: string): Promise<GroundResponse> {
  const r = await axios.post(ROUTES.VIDEO_GROUND(id), { query });
  return r.data?.data;
}

export async function searchVideo(id: string, query: string) {
  const r = await axios.post(ROUTES.VIDEO_SEARCH(id), { query });
  return r.data?.data;
}

export interface AnalyzeCitation {
  t_start: number;
  t_end: number;
  segment_idx: number;
}

export interface AnalyzeResponse {
  video_id: string;
  question: string;
  answer: string;
  citations: AnalyzeCitation[];
  used_windows: number;
  used_segments: number;
  modality?: VideoModality | null;
}

export async function askVideo(
  id: string,
  question: string,
  t_start?: number,
  t_end?: number,
): Promise<AnalyzeResponse> {
  const r = await axios.post(ROUTES.VIDEO_QA(id), { question, t_start, t_end });
  return r.data?.data;
}

export async function editVideo(id: string, clips: Array<{ t_start: number; t_end: number }>) {
  const r = await axios.post(ROUTES.VIDEO_EDIT(id), { clips });
  return r.data?.data;
}

// -- Cross-corpus search + segments (Playground) --

export interface CorpusShot extends ShotResult {
  video_id: string;
  original_filename: string;
  video_duration_s: number | null;
  ocr_text?: string;
  audio_tags?: Array<{ label: string; score: number }>;
}

export interface CorpusSearchResponse {
  query: string;
  group_by: "clip" | "video";
  shots: CorpusShot[];
}

export async function searchCorpus(params: {
  query: string;
  top_n?: number;
  group_by?: "clip" | "video";
}): Promise<CorpusSearchResponse> {
  const r = await axios.post(ROUTES.VIDEOS_SEARCH, {
    query: params.query,
    top_n: params.top_n ?? 10,
    group_by: params.group_by ?? "clip",
  });
  return r.data?.data;
}

/** @Entity image-as-query: find moments across the corpus that look like the
 *  supplied image. `image` is a base64 data URL. */
export async function searchCorpusByImage(params: {
  image: string;
  top_n?: number;
  group_by?: "clip" | "video";
}): Promise<CorpusSearchResponse> {
  const r = await axios.post(ROUTES.VIDEOS_SEARCH_IMAGE, {
    image: params.image,
    top_n: params.top_n ?? 10,
    group_by: params.group_by ?? "clip",
  });
  return r.data?.data;
}

export interface SegmentItem {
  idx: number;
  t_start: number;
  t_end: number;
  asr_text: string;
}

export interface SegmentListResponse {
  video_id: string;
  duration_s: number | null;
  segments: SegmentItem[];
}

export async function listSegments(id: string): Promise<SegmentListResponse> {
  const r = await axios.get(ROUTES.VIDEO_SEGMENTS(id));
  return r.data?.data;
}

// -- Segment Builder (multi-track) --

export interface SegmentFieldSpec {
  name: string;
  type?: "string" | "number" | "boolean";
  description?: string;
  enum?: string[];
}

export interface SegmentDefinition {
  id: string;
  description: string;
  fields: SegmentFieldSpec[];
  /** Per-definition time-range filter. e.g. ["0-10", "30-45"]. */
  time_ranges?: string[];
  /** Optional base64 image (data: URL) attached to the description. */
  image_attachment?: string;
}

export interface SegmentRunRequest {
  definitions: SegmentDefinition[];
  start_s?: number;
  end_s?: number;
  min_duration_s?: number;
  max_duration_s?: number;
}

export interface TrackSegment {
  t_start: number;
  t_end: number;
  metadata: Record<string, unknown>;
}

export interface SegmentTrack {
  definition_id: string;
  implemented: boolean;
  segments: TrackSegment[];
}

export interface SegmentRunResponse {
  video_id: string;
  duration_s: number | null;
  tracks: SegmentTrack[];
}

export async function runSegment(
  id: string,
  body: SegmentRunRequest,
): Promise<SegmentRunResponse> {
  const r = await axios.post(ROUTES.VIDEO_SEGMENT_RUN(id), body);
  return r.data?.data;
}

// -- Recommendations (UC #11) --

export interface SimilarVideoItem {
  video_id: string;
  original_filename: string;
  duration_s: number | null;
  shot_count: number | null;
  score: number;
}

export interface SimilarVideosResponse {
  video_id: string;
  results: SimilarVideoItem[];
  reason?: string;
}

export async function getSimilarVideos(id: string, topK = 5): Promise<SimilarVideosResponse> {
  const r = await axios.get(ROUTES.VIDEO_SIMILAR(id), { params: { top_k: topK } });
  return r.data?.data;
}

// -- Auto-highlights (UC #4) --

export interface HighlightsResponse {
  video_id: string;
  duration_s: number | null;
  moments: Span[];
  shots?: ShotResult[];                       // legacy backend only
  modality_used?: "visual" | "audio";
  query_used: string;
}

export async function getHighlights(id: string, topK = 10): Promise<HighlightsResponse> {
  const r = await axios.get(ROUTES.VIDEO_HIGHLIGHTS(id), { params: { top_k: topK } });
  return r.data?.data;
}

// -- Moderation (UC #14) --

export interface FlaggedShot {
  idx: number;
  t_start: number;
  t_end: number;
  nsfw_score: number;
  toxic_score: number;
  asr_text: string;
}

export interface ModerateResponse {
  video_id: string;
  threshold: number;
  summary: { max_nsfw: number; max_toxic: number; flagged_count: number };
  flagged_shots: FlaggedShot[];
}

export async function getModeration(id: string, threshold = 0.5): Promise<ModerateResponse> {
  const r = await axios.get(ROUTES.VIDEO_MODERATE(id), { params: { threshold } });
  return r.data?.data;
}

// -- Audio events (UC #15) --

export interface AudioTag { label: string; score: number; }

export interface SoundShot {
  idx: number;
  t_start: number;
  t_end: number;
  audio_tags: AudioTag[];
  asr_text: string;
}

export interface SoundsResponse {
  video_id: string;
  tag: string | null;
  shots: SoundShot[];
}

export async function getSounds(id: string, tag?: string): Promise<SoundsResponse> {
  const r = await axios.get(ROUTES.VIDEO_SOUNDS(id), { params: tag ? { tag } : {} });
  return r.data?.data;
}
