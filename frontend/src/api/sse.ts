// Fetch-based Server-Sent-Events reader.
//
// The native EventSource only supports GET and cannot send a JSON body, but the
// backend streams over a POST (/api/chat/turn) as well as a GET (/api/deploy/logs).
// This helper reads the response body as a stream, splits on the SSE frame
// delimiter, parses each `data:` line as JSON, and invokes `onFrame`.

export interface StreamOptions<T> {
  method?: 'GET' | 'POST';
  body?: unknown;
  signal?: AbortSignal;
  onFrame: (frame: T) => void;
}

export async function streamSSE<T>(path: string, opts: StreamOptions<T>): Promise<void> {
  const { method = 'GET', body, signal, onFrame } = opts;

  const res = await fetch(path, {
    method,
    credentials: 'include',
    headers: {
      Accept: 'text/event-stream',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`SSE request failed: ${res.status} ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const flush = (chunk: string) => {
    buffer += chunk;
    // Frames are separated by a blank line. Handle both \n\n and \r\n\r\n.
    let sep = findSeparator(buffer);
    while (sep.index !== -1) {
      const rawFrame = buffer.slice(0, sep.index);
      buffer = buffer.slice(sep.index + sep.length);
      emit(rawFrame, onFrame);
      sep = findSeparator(buffer);
    }
  };

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      flush(decoder.decode(value, { stream: true }));
    }
    // Emit any trailing frame that wasn't terminated by a blank line.
    if (buffer.trim().length > 0) emit(buffer, onFrame);
  } finally {
    reader.releaseLock();
  }
}

function findSeparator(buffer: string): { index: number; length: number } {
  const lf = buffer.indexOf('\n\n');
  const crlf = buffer.indexOf('\r\n\r\n');
  if (lf === -1 && crlf === -1) return { index: -1, length: 0 };
  if (crlf === -1 || (lf !== -1 && lf < crlf)) return { index: lf, length: 2 };
  return { index: crlf, length: 4 };
}

function emit<T>(rawFrame: string, onFrame: (frame: T) => void): void {
  for (const line of rawFrame.split(/\r?\n/)) {
    const trimmed = line.trimStart();
    if (!trimmed.startsWith('data:')) continue;
    const payload = trimmed.slice(5).trim();
    if (!payload) continue;
    try {
      onFrame(JSON.parse(payload) as T);
    } catch {
      // Ignore keep-alive / non-JSON comments.
    }
  }
}
