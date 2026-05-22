export const ROUTES = {
  // Auth
  REGISTER: "/auth/register",
  LOGIN: "/auth/login",
  RENEW_TOKEN: "/auth/renew",
  ME: "/users/me",

  // Videos
  VIDEOS: "/videos",
  VIDEO: (id: string) => `/videos/${id}`,
  VIDEO_STREAM: (id: string) => `/videos/${id}/stream`,
  VIDEO_THUMB: (id: string, idx: number) => `/videos/${id}/thumb/${idx}`,
  VIDEO_GROUND: (id: string) => `/videos/${id}/ground`,
  VIDEO_SEARCH: (id: string) => `/videos/${id}/search`,
  VIDEO_QA: (id: string) => `/videos/${id}/qa`,
  VIDEO_EDIT: (id: string) => `/videos/${id}/edit`,
  VIDEO_SEGMENTS: (id: string) => `/videos/${id}/segments`,
  VIDEO_SEGMENT_RUN: (id: string) => `/videos/${id}/segment`,
  VIDEOS_SEARCH: "/videos/search",
  VIDEO_SIMILAR: (id: string) => `/videos/${id}/similar`,
  VIDEO_HIGHLIGHTS: (id: string) => `/videos/${id}/highlights`,
  VIDEO_MODERATE: (id: string) => `/videos/${id}/moderate`,
  VIDEO_SOUNDS: (id: string) => `/videos/${id}/sounds`,

  // Chat
  CHAT_STREAM: "/chat/stream",
  CONVERSATIONS: "/conversations",
  CONVERSATION: (id: string) => `/conversations/${id}`,

  // Usage
  USAGE_ME: "/usage/me",
} as const;

export const TOKEN_KEYS = {
  ACCESS: "tl_jockey_access",
  REFRESH: "tl_jockey_refresh",
} as const;
