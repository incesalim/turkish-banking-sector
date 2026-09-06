/** Resolve an attachment only through its retained official archive relationship. */
import { CORPUS_PREFIX, parseCorpusRevision, type CorpusBucket, type FilingIdentity } from "./document-corpus";
import { getOriginReview } from "./document-origin";

const record = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

export async function getRelatedRevision(bucket: CorpusBucket, filing: FilingIdentity, memberHash: string) {
  if (!/^[a-f0-9]{64}$/.test(memberHash)) throw new Error("Invalid related document hash");
  const origin = await getOriginReview(bucket, filing);
  const members = origin?.selection?.unselected_pdf_members?.filter(m => m.sha256 === memberHash) ?? [];
  if (!origin?.transport || !origin.origin_pdf || members.length !== 1) {
    throw new Error("Related document is absent or ambiguous in the verified source archive");
  }
  const member = members[0];
  const key = `${CORPUS_PREFIX}related/${filing.bank_ticker}/${filing.period}/${filing.kind}/${origin.transport.sha256}/${memberHash}.json`;
  const object = await bucket.get(key);
  if (!object) return null;
  if (object.size > 8_000_000) throw new Error("Oversized related document index");
  const index: unknown = await object.json();
  const relation = record(index) ? index.relationship : null;
  if (!record(relation) || relation.schema_version !== "related-source-binding-1"
      || relation.relationship !== "other_pdf_in_same_registered_source_archive" || relation.semantically_verified !== false
      || !record(relation.filing) || Object.entries(filing).some(([k, v]) => (relation.filing as Record<string, unknown>)[k] !== v)
      || relation.transport_sha256 !== origin.transport.sha256 || relation.transport_key !== origin.transport.key
      || relation.primary_pdf_sha256 !== origin.origin_pdf.sha256 || relation.primary_member_name !== origin.selection?.archive_member
      || !record(relation.member) || Object.entries(member).some(([k, v]) => (relation.member as Record<string, unknown>)[k] !== v)) {
    throw new Error("Related document index differs from its official source archive");
  }
  const revision = parseCorpusRevision(index, filing);
  // For ordinary PDF members, the origin's independently retained member hash
  // binds the current source directly. A wrapped member needs a separate
  // verified wrapper binding; never accept another valid filing revision here.
  if (revision && revision.source.pdf_sha256 !== memberHash) {
    throw new Error("Related PDF bytes cannot be matched directly to the retained archive member");
  }
  if (revision && (!record(index) || !record(index.current) || index.current.semantic_verification !== "not_performed")) {
    throw new Error("Related source claims unsupported semantic approval");
  }
  return revision;
}
