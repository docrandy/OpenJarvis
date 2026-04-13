/**
 * Text-to-Speech via OpenAI TTS API.
 * Reads the API key from localStorage (same key the Settings page stores).
 */

const STORAGE_KEY = "openjarvis-openai-key";
const TTS_URL = "https://api.openai.com/v1/audio/speech";

export interface TTSOptions {
  voice?: string; // alloy, echo, fable, onyx, nova, shimmer
  model?: string; // tts-1 or tts-1-hd
  speed?: number; // 0.25 to 4.0
}

const defaults: Required<TTSOptions> = {
  voice: "onyx",
  model: "tts-1",
  speed: 1.0,
};

/** Check whether TTS is available (OpenAI key exists). */
export function ttsAvailable(): boolean {
  return !!localStorage.getItem(STORAGE_KEY);
}

/** Convert text to speech and auto-play it. Returns the audio element. */
export async function speakText(
  text: string,
  opts?: TTSOptions,
  signal?: AbortSignal,
): Promise<HTMLAudioElement | null> {
  const apiKey = localStorage.getItem(STORAGE_KEY);
  if (!apiKey || !text.trim()) return null;

  const { voice, model, speed } = { ...defaults, ...opts };

  // Truncate to ~4000 chars (OpenAI TTS limit is 4096)
  const input = text.slice(0, 4000);

  const res = await fetch(TTS_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ model, input, voice, speed }),
    signal,
  });

  if (!res.ok) {
    console.warn("TTS failed:", res.status, await res.text());
    return null;
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);

  audio.addEventListener("ended", () => URL.revokeObjectURL(url), {
    once: true,
  });
  await audio.play();
  return audio;
}
