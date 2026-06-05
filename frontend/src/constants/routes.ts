export const ROUTES = {
  // Auth
  REGISTER: "/auth/register",
  LOGIN: "/auth/login",
  GOOGLE_AUTH: "/auth/google",
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
  VIDEOS_SEARCH_IMAGE: "/videos/search/image",
  VIDEO_SEARCH_IMAGE: (id: string) => `/videos/${id}/search/image`,
  VIDEO_SIMILAR: (id: string) => `/videos/${id}/similar`,
  VIDEO_HIGHLIGHTS: (id: string) => `/videos/${id}/highlights`,
  VIDEO_MODERATE: (id: string) => `/videos/${id}/moderate`,
  VIDEO_SOUNDS: (id: string) => `/videos/${id}/sounds`,

  // Indexes (lecture series / collections)
  INDEXES: "/indexes",
  INDEX: (id: string) => `/indexes/${id}`,
  INDEX_VIDEOS: (id: string) => `/indexes/${id}/videos`,
  INDEX_VIDEO: (id: string, videoId: string) => `/indexes/${id}/videos/${videoId}`,
  INDEX_SEARCH: (id: string) => `/indexes/${id}/search`,
  // Phase 2a KG endpoints — separate from text retrieval (intentional)
  INDEX_CONCEPTS_SEARCH: (id: string) => `/indexes/${id}/concepts/search`,
  INDEX_ENTITY_MENTIONS: (id: string, entityId: string) =>
    `/indexes/${id}/entities/${entityId}/mentions`,
  INDEX_ENTITY_RELATED: (id: string, entityId: string) =>
    `/indexes/${id}/entities/${entityId}/related`,

  // Chat
  CHAT_STREAM: "/chat/stream",
  CONVERSATIONS: "/conversations",
  CONVERSATION: (id: string) => `/conversations/${id}`,

  // Usage
  USAGE_ME: "/usage/me",

  // Billing
  BILLING_PLANS: "/billing/plans",
  BILLING_SUBSCRIPTION: "/billing/subscription",
  BILLING_CHECKOUT: "/billing/checkout",
} as const;

export const TOKEN_KEYS = {
  ACCESS: "tl_jockey_access",
  REFRESH: "tl_jockey_refresh",
} as const;
