import { API_BASE, ApiError, authenticatedHeaders } from "./client";

interface SseFrame {
  id?: string;
  data?: string;
}

function parseFrame(raw: string): SseFrame {
  const frame: SseFrame = {};
  const data: string[] = [];
  for (const line of raw.split(/\r?\n/)) {
    if (line.startsWith("id:")) frame.id = line.slice(3).trimStart();
    if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (data.length) frame.data = data.join("\n");
  return frame;
}

export async function streamSse<T>(
  path: string,
  onEvent: (event: T, eventId: string | undefined) => void,
  options: { signal: AbortSignal; lastEventId?: string },
): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      Accept: "text/event-stream",
      ...authenticatedHeaders(),
      ...(options.lastEventId ? { "Last-Event-ID": options.lastEventId } : {}),
    },
    signal: options.signal,
  });
  if (!response.ok || !response.body) {
    throw new ApiError(
      "Agent event stream is unavailable.",
      undefined,
      "SSE_UNAVAILABLE",
      response.status,
    );
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? "";
    for (const raw of frames) {
      const frame = parseFrame(raw);
      if (frame.data) onEvent(JSON.parse(frame.data) as T, frame.id);
    }
    if (done) return;
  }
}
