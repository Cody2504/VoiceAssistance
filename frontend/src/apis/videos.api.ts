import axios from "axios";
import { ROUTES } from "@/constants/routes";

export interface VideoSummary {
  id: string;
  user_id: string;
  original_filename: string;
  duration_s: number | null;
  status: "queued" | "processing" | "ready" | "error";
  shot_count: number | null;
  error: string | null;
  created_at: string;
}

export async function listVideos(): Promise<VideoSummary[]> {
  const r = await axios.get(ROUTES.VIDEOS);
  return r.data?.data ?? [];
}

export async function getVideo(id: string): Promise<VideoSummary> {
  const r = await axios.get(ROUTES.VIDEO(id));
  return r.data?.data;
}

export async function getStreamUrl(id: string): Promise<string> {
  const r = await axios.get(ROUTES.VIDEO_STREAM(id));
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

export interface GroundResponse {
  video_id: string;
  query: string;
  shots: ShotResult[];
  spans: Span[];
}

export async function groundVideo(id: string, query: string): Promise<GroundResponse> {
  const r = await axios.post(ROUTES.VIDEO_GROUND(id), { query });
  return r.data?.data;
}

export async function searchVideo(id: string, query: string) {
  const r = await axios.post(ROUTES.VIDEO_SEARCH(id), { query });
  return r.data?.data;
}

export async function askVideo(id: string, question: string, t_start?: number, t_end?: number) {
  const r = await axios.post(ROUTES.VIDEO_QA(id), { question, t_start, t_end });
  return r.data?.data;
}

export async function editVideo(id: string, clips: Array<{ t_start: number; t_end: number }>) {
  const r = await axios.post(ROUTES.VIDEO_EDIT(id), { clips });
  return r.data?.data;
}
