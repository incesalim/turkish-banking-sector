/** Independent official-source observations; byte agreement never approves contents. */
import { CORPUS_PREFIX, type CorpusBucket, type FilingIdentity } from "./document-corpus";
import { readRecoveryArtifact } from "./document-recovery";

type Artifact = { key: string; sha256: string; bytes: number };
export type OriginReview = {
  schema_version: "document-origin-review-1"; filing: FilingIdentity; checked_at: string;
  status: "matches_acquired_bytes" | "same_pdf_after_acquisition_wrapper" | "different_pdf_revision"
    | "acquisition_missing" | "origin_unavailable" | "origin_needs_review";
  source_url: string; semantically_verified: false; error?: string;
  acquisition: { sha256: string; bytes: number } | null;
  transport: Artifact | null; origin_pdf: Artifact | null;
  origin_identity?: { status: string }; related_pdf_content_capture?: string;
  selection?: { unselected_pdf_members?: { name: string; bytes: number; sha256: string }[] };
};
const record = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const hash = (v: unknown): v is string => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
const count = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v > 0;
const sameFiling = (v: unknown, f: FilingIdentity) => record(v) && Object.entries(f).every(([k, value]) => v[k] === value);
const time = (v: unknown): v is string => typeof v === "string" && /(?:Z|\+00:00)$/.test(v) && Number.isFinite(Date.parse(v));
const statuses = new Set(["matches_acquired_bytes", "same_pdf_after_acquisition_wrapper", "different_pdf_revision",
  "acquisition_missing", "origin_unavailable", "origin_needs_review"]);

export async function getOriginReview(bucket: CorpusBucket, filing: FilingIdentity): Promise<OriginReview | null> {
  const base = `${CORPUS_PREFIX}origins/${filing.bank_ticker}/${filing.period}/${filing.kind}/`;
  const object = await bucket.get(base + "index.json");
  if (!object) return null;
  if (object.size > 4_000_000) throw new Error("Oversized origin index");
  const index: unknown = await object.json();
  if (!record(index) || index.schema_version !== "document-origin-index-1" || !sameFiling(index.filing, filing)
      || index.semantically_verified !== false || !Array.isArray(index.revisions) || !record(index.current)) {
    throw new Error("Invalid origin index binding");
  }
  const current = index.current;
  if (!hash(current.sha256) || current.key !== `${base}${current.sha256}.json` || !count(current.bytes)
      || !time(current.checked_at) || !statuses.has(String(current.status))
      || !index.revisions.some(r => record(r) && ["key", "sha256", "bytes", "checked_at", "status", "acquisition_sha256"]
        .every(k => r[k] === current[k]))) throw new Error("Invalid origin revision");
  const bytes = await readRecoveryArtifact(bucket, current as Artifact);
  const value: unknown = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  if (!record(value) || value.schema_version !== "document-origin-review-1" || !sameFiling(value.filing, filing)
      || value.semantically_verified !== false || value.status !== current.status || value.checked_at !== current.checked_at
      || typeof value.source_url !== "string" || !/^https?:\/\//.test(value.source_url)
      || value.error !== undefined && typeof value.error !== "string") throw new Error("Origin receipt binding mismatch");
  if (value.acquisition !== null && (!record(value.acquisition) || !hash(value.acquisition.sha256)
      || !count(value.acquisition.bytes))) throw new Error("Invalid acquired-source observation");
  if ((record(value.acquisition) ? value.acquisition.sha256 : null) !== current.acquisition_sha256) {
    throw new Error("Origin acquisition differs from its index");
  }
  for (const name of ["transport", "origin_pdf"]) {
    const entry = value[name];
    if (entry === null) continue;
    if (!record(entry) || !hash(entry.sha256) || !count(entry.bytes)
        || entry.key !== (name === "transport" ? `${CORPUS_PREFIX}transports/${entry.sha256}/original.bin`
          : `${CORPUS_PREFIX}sources/${entry.sha256}/original.pdf`)) throw new Error("Invalid origin artifact key");
  }
  if (value.origin_identity !== undefined && (!record(value.origin_identity) || typeof value.origin_identity.status !== "string")) {
    throw new Error("Invalid origin identity observation");
  }
  if (value.selection !== undefined) {
    if (!record(value.selection)) throw new Error("Invalid origin archive selection");
    const members = value.selection.unselected_pdf_members;
    if (members !== undefined && (!Array.isArray(members) || members.some(m => !record(m)
        || typeof m.name !== "string" || !count(m.bytes) || !hash(m.sha256)))) throw new Error("Invalid related PDF members");
  }
  const acquiredHash = record(value.acquisition) ? value.acquisition.sha256 : null;
  const originHash = record(value.origin_pdf) ? value.origin_pdf.sha256 : null;
  if (value.status === "matches_acquired_bytes" && (!acquiredHash || acquiredHash !== originHash)
      || value.status === "different_pdf_revision" && (!acquiredHash || !originHash || acquiredHash === originHash)
      || value.status === "acquisition_missing" && (acquiredHash !== null || !originHash)
      || value.status === "origin_unavailable" && (value.transport !== null || value.origin_pdf !== null)
      || value.status === "same_pdf_after_acquisition_wrapper" && (!acquiredHash || !originHash || !record(value.acquisition_wrapper))) {
    throw new Error("Origin comparison contradicts observed source hashes");
  }
  return value as unknown as OriginReview;
}
