/**
 * Client for the standalone S3 browser backend (`scripts/s3_browser.py`).
 *
 * Runs separately from the main video-service gateway — defaults to
 * http://localhost:8765 but can be overridden via VITE_S3_BROWSER_URL.
 */
import axios from "axios";

const BASE = import.meta.env.VITE_S3_BROWSER_URL ?? "http://localhost:8765";

export interface S3Item {
  key: string;             // e.g. "videos/SAT_table.mp4"
  name: string;            // basename, e.g. "SAT_table.mp4"
  size: number;            // bytes
  last_modified: string;   // ISO timestamp
  duration_s: number | null;
  thumb_url: string | null; // presigned URL to the matching thumbs/<stem>.jpg, or null
}

export interface S3ListResponse {
  bucket: string;
  count: number;
  items: S3Item[];
}

export async function listS3Objects(): Promise<S3ListResponse> {
  const r = await axios.get<S3ListResponse>(`${BASE}/api/objects`);
  return r.data;
}

export async function presignS3(key: string): Promise<string> {
  const r = await axios.get<{ url: string; expires_in: number }>(
    `${BASE}/api/presign`,
    { params: { key } },
  );
  return r.data.url;
}
