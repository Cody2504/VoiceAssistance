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
  VIDEO_GROUND: (id: string) => `/videos/${id}/ground`,
  VIDEO_SEARCH: (id: string) => `/videos/${id}/search`,
  VIDEO_QA: (id: string) => `/videos/${id}/qa`,
  VIDEO_EDIT: (id: string) => `/videos/${id}/edit`,

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
