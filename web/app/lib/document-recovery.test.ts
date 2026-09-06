import { readFileSync } from "node:fs";
import { gunzipSync, gzipSync } from "node:zlib";
import { createHash } from "node:crypto";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { getRecoveryIndex, readRecoveryPage } from "./document-recovery";
import type { CorpusBucket } from "./document-corpus";

const mocks = vi.hoisted(() => ({ gate: vi.fn(), context: vi.fn() }));
vi.mock("@opennextjs/cloudflare", () => ({ getCloudflareContext: mocks.context }));
vi.mock("@/app/lib/admin-auth", () => ({ requireAdminOr403: mocks.gate }));
vi.mock("@/app/lib/document-corpus", () => import("./document-corpus"));
vi.mock("@/app/lib/document-recovery", () => import("./document-recovery"));
import { GET } from "../api/admin/document-recovery/route";

const fixture = JSON.parse(readFileSync(new URL("../../../tests/fixtures/document_recovery_wire.json", import.meta.url), "utf8"));
const source = fixture.core_index.current;
const stream = (bytes: Uint8Array) => new ReadableStream<Uint8Array>({ start(c) { c.enqueue(bytes); c.close(); } });
const objects = Object.fromEntries(Object.entries(fixture.objects_gzip).map(([key, value]) =>
  [key, gunzipSync(Buffer.from(value as string, "base64"))]));
function bucket(index = fixture.index, mutate?: (b: Buffer) => Buffer): CorpusBucket {
  return { get: vi.fn(async (key: string) => {
    if (key.includes("/filings/")) return { size: 2000, uploaded: new Date(), body: stream(new Uint8Array()), json: async () => fixture.core_index };
    if (key.includes("/recovery/TEST/")) return { size: 2000, uploaded: new Date(), body: stream(new Uint8Array()), json: async () => index };
    const original = objects[key];
    if (!original) return null;
    const bytes = mutate ? mutate(original) : original;
    return { size: original.length, uploaded: new Date(), body: stream(bytes), json: async () => JSON.parse(bytes.toString()) };
  }) } as unknown as CorpusBucket;
}
const entry = fixture.index.pages["1"].current.artifacts.page;
const url = "https://test/api/admin/document-recovery?filing=TEST%7C2026Q1%7Cconsolidated&page=1";

describe("source-bound recovery wire format", () => {
  it("reads the Python-produced packet and retains disclosed zero", async () => {
    expect(await getRecoveryIndex(bucket(), source)).toEqual(fixture.index);
    const value = await readRecoveryPage(bucket(), entry, source, 1);
    expect(value.view.lines[0].text).toBe("Disclosed zero 0 and unknown");
    expect(value.semantically_verified).toBe(false);
  });
  it("rejects another source's index, page number and arbitrary storage keys", async () => {
    const index = structuredClone(fixture.index);
    index.source.pdf_sha256 = "b".repeat(64);
    await expect(getRecoveryIndex(bucket(index), source)).rejects.toThrow("source mismatch");
    const wrong = structuredClone(fixture.index);
    wrong.pages["1"].current.artifacts.page.key = "private/unrelated.json";
    await expect(getRecoveryIndex(bucket(wrong), source)).rejects.toThrow("outside");
    await expect(readRecoveryPage(bucket(), entry, source, 2)).rejects.toThrow("source mismatch");
  });
  it("rejects changed bytes and source identity even if a new checksum is supplied", async () => {
    await expect(readRecoveryPage(bucket(fixture.index, b => Buffer.concat([b, Buffer.from("changed")])), entry, source, 1)).rejects.toThrow();
    const packet = JSON.parse(gunzipSync(objects[entry.key]).toString());
    packet.source.pdf_sha256 = "a".repeat(64);
    const bytes = gzipSync(JSON.stringify(packet));
    const bad = { ...entry, bytes: bytes.length, sha256: createHash("sha256").update(bytes).digest("hex") };
    const mocked = { get: async () => ({ size: bytes.length, body: stream(bytes) }) } as unknown as CorpusBucket;
    await expect(readRecoveryPage(mocked, bad, source, 1)).rejects.toThrow("source mismatch");
  });
});

describe("private recovery route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.gate.mockResolvedValue({ identity: { email: "test" } });
    mocks.context.mockResolvedValue({ env: { AUDIT_DOCUMENTS: bucket() } });
  });
  it("blocks anonymous reads before accessing storage", async () => {
    mocks.gate.mockResolvedValue({ response: Response.json({}, { status: 403 }) });
    const r = await GET(new Request(url));
    expect(r.status).toBe(403);
    expect(r.headers.get("Cache-Control")).toBe("private, no-store");
    expect(mocks.context).not.toHaveBeenCalled();
  });
  it("serves a verified page and its retained image-bearing PDF privately", async () => {
    const r = await GET(new Request(url));
    expect(r.status).toBe(200);
    expect((await r.json()).page.view.lines[0].text).toContain("zero 0");
    const pdf = await GET(new Request(url + "&artifact=ocr-pdf"));
    expect(pdf.headers.get("Content-Type")).toBe("application/pdf");
    expect(pdf.headers.get("Cache-Control")).toBe("private, no-store");
    expect(Buffer.from(await pdf.arrayBuffer()).subarray(0, 5).toString()).toBe("%PDF-");
  });
  it("does not reuse another PDF revision or treat missing recovery as zero text", async () => {
    mocks.context.mockResolvedValue({ env: { AUDIT_DOCUMENTS: bucket({ ...fixture.index, pages: {} }) } });
    expect(await (await GET(new Request(url))).json()).toEqual({ status: "not_started" });
    const index = structuredClone(fixture.index);
    index.source.pdf_sha256 = "b".repeat(64);
    mocks.context.mockResolvedValue({ env: { AUDIT_DOCUMENTS: bucket(index) } });
    expect((await GET(new Request(url))).status).toBe(503);
  });
});
