/** Read recovery only for the current source revision; no user-supplied keys. */
import { CORPUS_PREFIX, type CorpusBucket, type CorpusRevision } from "./document-corpus";

type Artifact = { key: string; sha256: string; bytes: number };
type RecoveryRevision = { page: number; artifacts: Record<string, Artifact>; semantically_verified: false };
type RecoveryRow = { current: RecoveryRevision | null; last_attempt?: { status: string; error?: string } };
type RecoveryIndex = { pages: Record<string, RecoveryRow> };
export type RecoveryPage = { schema_version: "source-recovery-page-1"; page: number;
  source: { pdf_sha256: string }; status: "recovery_candidates"; semantically_verified: false;
  view: { lines: { id: string; text: string; word_ids: number[]; bbox: number[] }[];
    vector_comparisons: { drawing_id: number; vector_text: string; ocr_text: string | null;
      status: "missing_ocr" | "exact_agreement" | "disagreement"; bbox: number[] }[] };
};
const record = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const hash = (v: unknown): v is string => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);

export async function getRecoveryIndex(bucket: CorpusBucket, source: CorpusRevision): Promise<RecoveryIndex | null> {
  const f = source.source;
  const object = await bucket.get(`${CORPUS_PREFIX}recovery/${f.bank_ticker}/${f.period}/${f.kind}/${f.pdf_sha256}.json`);
  if (!object) return null;
  if (object.size > 8_000_000) throw new Error("Oversized recovery index");
  const value: unknown = await object.json();
  if (!record(value) || value.schema_version !== "corpus-recovery-index-1" || !record(value.source)
      || value.semantically_verified !== false || !record(value.pages)
      || ["bank_ticker", "period", "kind", "pdf_sha256"].some(k => (value.source as Record<string, unknown>)[k] !== f[k as keyof typeof f])) {
    throw new Error("Recovery index source mismatch");
  }
  for (const [number, row] of Object.entries(value.pages)) {
    if (!/^\d+$/.test(number) || Number(number) < 1 || Number(number) > source.page_count || !record(row)) {
      throw new Error("Invalid recovery page");
    }
    if (row.current === null) continue;
    const r = row.current;
    if (!record(r) || r.page !== Number(number) || r.semantically_verified !== false || !record(r.artifacts)) {
      throw new Error("Invalid recovery revision");
    }
    for (const [name, entry] of Object.entries(r.artifacts)) {
      if (!record(entry) || !hash(entry.sha256) || typeof entry.key !== "string"
          || typeof entry.bytes !== "number" || !Number.isSafeInteger(entry.bytes) || entry.bytes < 1) {
        throw new Error("Invalid recovery artifact");
      }
      const suffix = { page: "recovery.json.gz", ocr_pdf: "ocr.pdf", atlas: "atlas.json.gz" }[name];
      const expected = name === "reference_pdf" ? `${CORPUS_PREFIX}sources/${entry.sha256}/original.pdf`
        : suffix ? `${CORPUS_PREFIX}sources/${f.pdf_sha256}/recovery/${entry.sha256}.${suffix}` : null;
      if (entry.key !== expected) throw new Error("Recovery key is outside its source");
    }
    if (!r.artifacts.page || !r.artifacts.ocr_pdf) throw new Error("Recovery artifacts are missing");
  }
  return value as unknown as RecoveryIndex;
}

async function boundedBytes(stream: ReadableStream<Uint8Array>, limit: number): Promise<Uint8Array> {
  const reader = stream.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const part = await reader.read();
      if (part.done) break;
      length += part.value.length;
      if (length > limit) throw new Error("Oversized recovery artifact");
      chunks.push(part.value);
    }
  } finally { await reader.cancel(); }
  const result = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.length; }
  return result;
}

export async function readRecoveryArtifact(bucket: CorpusBucket, entry: Artifact): Promise<Uint8Array> {
  const object = await bucket.get(entry.key);
  if (!object || object.size !== entry.bytes || entry.bytes > 24_000_000) throw new Error("Recovery artifact missing or oversized");
  const bytes = await boundedBytes(object.body, entry.bytes);
  const digest = await crypto.subtle.digest("SHA-256", new Uint8Array(bytes).buffer);
  const actual = Array.from(new Uint8Array(digest), v => v.toString(16).padStart(2, "0")).join("");
  if (actual !== entry.sha256 || bytes.length !== entry.bytes) throw new Error("Recovery checksum mismatch");
  return bytes;
}

export async function readRecoveryPage(bucket: CorpusBucket, entry: Artifact, source: CorpusRevision, page: number) {
  const bytes = await readRecoveryArtifact(bucket, entry);
  const compressed = new Blob([new Uint8Array(bytes).buffer]).stream();
  const expanded = await boundedBytes(compressed.pipeThrough(new DecompressionStream("gzip")), 48_000_000);
  const value: unknown = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(expanded));
  if (!record(value) || value.schema_version !== "source-recovery-page-1" || value.page !== page
      || value.status !== "recovery_candidates" || value.semantically_verified !== false
      || !record(value.source) || ["bank_ticker", "period", "kind", "pdf_sha256"].some(k =>
        (value.source as Record<string, unknown>)[k] !== source.source[k as keyof typeof source.source])
      || !record(value.view) || !Array.isArray(value.view.lines) || !Array.isArray(value.view.vector_comparisons)) {
    throw new Error("Recovery page source mismatch");
  }
  return value as unknown as RecoveryPage;
}
