# tl-jockey frontend

React 19 + Vite + TypeScript + Tailwind v4 + Radix. Talks to the backend at `http://localhost:85/api/v1`
through the Nginx gateway.

```bash
npm install
npm run dev      # http://localhost:5173
```

## Layout

```
src/
  apis/          axios clients for each backend service
  components/    ui primitives (shadcn-style), chat thread, video player + timeline
  contexts/      AuthContext (Context + localStorage, no Redux)
  hooks/         useVideoStatus (polls /videos/{id} while indexing)
  pages/         auth / library / video / chat / profile
  utils/         setupAxios (token-refresh interceptor queue)
  i18n/          en + vi locales
```

## SSE chat consumer

`apis/chat.api.ts` opens a POST to `/chat/stream` and parses the SSE event stream from `agent-service`:
- `event: thought` → render in ThoughtCard (planner/supervisor reasoning)
- `event: tool_call` / `tool_result` → render a tool-use chip; `ground_video` results populate the timeline
- `event: message` → stream into the assistant bubble
- `event: end` → finalise turn
