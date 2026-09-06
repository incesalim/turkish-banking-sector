# Complete audit document corpus

Status: active implementation, begun 2026-09-06.

## Objective and scope

Preserve every table and every text passage in the registered bank audit-report
corpus, across banks, periods and reporting bases. Preserve source structure,
provenance and qualifications so tables can later become website time series
and narrative can support analyst research. Complete the registered corpus
first; expand to additional banks and earlier history afterward (user decision,
2026-09-06).

Existing task reports, successful jobs, extracted counts and internal accounting
identities are not evidence that the source was captured completely. Verify
against original PDFs and independently annotated source cases. No filing is
described as fully verified while any content region or required check remains
unresolved. Source contradictions are retained and flagged, never silently fixed
in the transcription layer.

The concurrent release-pipeline task owns the currently modified workflows,
`src/pipeline/`, release scripts and its migration. Keep this implementation
separate; do not stage or overwrite that task's changes.

## Verified starting observations

- Live R2 listing on 2026-09-06: 1,117 audit PDF objects, 38 banks,
  2022Q1 through 2026Q2. This counts acquired objects, not independently expected
  filings. The registered URL set and acquisition inventory must be reconciled.
- The local legacy capture has 1,095 filings. It cannot be accepted as the
  current corpus and does not store a PDF byte hash or extraction version.
- Routine `refresh-audit` captures a run-local ledger and discards it. The
  durable fleet ledger is written by a separate manual backfill. Detailed new
  filings therefore do not automatically accumulate in durable capture storage.
- The admin coverage matrix describes predefined analytical lanes. It does not
  establish whole-document capture coverage or show source-level verification.
- The legacy capture retains text lines and numerical table geometry; pure text
  tables and image/vector content require explicit handling. Successful numeric
  parsing does not establish preservation of all textual relationships.
- A source-verified QNB example preserves both printed percentages correctly
  but assigns an incorrect analytical role. Literal transcription and financial
  interpretation need separately testable contracts.

## Work sequence and acceptance

1. **Corpus inventory and immutable source identity.** Reconcile registered
   filings, acquisition objects and local inputs. Store original URL/object key,
   PDF SHA-256, byte count, bank/period/basis and revision association. Record
   missing sources and conflicting identities explicitly. Completeness must
   have a denominator independent of successful extraction.
2. **Independent source evidence and benchmark.** Preserve PyMuPDF source text
   and geometry without routing it through the existing table detector. Account
   for every text token, including duplicate occurrences, and every nontext
   region. Construct source-annotated real-PDF cases covering languages,
   rotation, wrapped and multi-page tables, prose, footnotes, text-only tables,
   outlines and scans. Verify the check itself with dropped/swapped content.
3. **Complete structured document representation.** Preserve document order,
   sections and nested headings; tables with row/column headers, original cell
   text and spans; paragraphs/lists; notes and references; page and bounding-box
   provenance; extraction method and explicit ambiguity. Keep residual content
   accessible. OCR/vision recovery must preserve source evidence and remain
   unverified until independently checked.
4. **Durable incremental processing.** Write per-source, versioned artifacts to
   R2; skip identical inputs and engine versions. Resume interrupted runs and
   retain failures. Rebuild searchable/structured views from those artifacts.
   Run fleet processing in Actions, keeping local execution to light probes
   and tests. A failed filing must not disappear behind a successful job total.
5. **Admin and analyst access.** Expose the expected/acquired/captured/verified
   distinction, stale versions, content gaps and source evidence in the admin
   panel. Provide queryable tables and structured prose with citations. Store
   large evidence in R2; limit D1 to useful indexes/status and approved derived
   data, with content comparison before writes.
6. **Corpus verification and series migration decision.** Run the independent
   checks across the registered corpus, investigate every unresolved class and
   publish an explicit readiness record. Verify new analytical questions against
   the source. Compare candidate series to current lanes by period, unit, basis
   and meaning; replace lanes only when the replacement has demonstrated the
   required coverage and correctness. Current serving lanes remain available
   during that comparison.

## Definition of done

Every expected filing has a traceable source or an evidenced acquisition gap.
Every acquired source version has durable, reproducible capture artifacts.
Every page's text and nontext content is accounted for. Every detected table,
paragraph and note is accessible with its source and structural context. Tests
exercise omission, duplication, misassociation, source changes and failed runs.
The admin view exposes unresolved work instead of collapsing it into a green
extraction status. Representative whole documents and new research questions
have been verified against rendered source pages, and remaining corpus issues
are enumerated. Completion is not inferred from a passing unit suite or a count
of detected tables.

## Execution record

- 2026-09-06: traced acquisition, capture, table derivation, prose, serving,
  admin coverage and workflow persistence. Confirmed first-stage scope with
  the user. Inspected live R2 object inventory read-only. Began independent
  inventory and source-evidence implementation.
- 2026-09-06: implemented immutable source evidence, source-bound candidate
  structure, per-filing R2 revision indexes and resumable publication. Candidate
  structure keeps all source text blocks, numeric table candidates, additional
  ruled text-only tables and nontext region references. Tests deliberately drop,
  duplicate, corrupt and swap content and interrupt uploads. None of these
  artifact-integrity checks certifies semantic completeness. Fleet publication,
  whole-document annotation and admin integration remain unfinished.
- 2026-09-06: visually verified QNB 2026Q1 solo PDF pages 45–46. Fixed the
  countercyclical-buffer role matcher to use the actual requirement row (0.01%),
  not a regulation reference inside the distinct 5.97% ratio. Added regression
  tests and reran the assembler; stored wide rows still require targeted rebuild.
- 2026-09-06: inspected the signed-in live admin panel. Its audit summary showed
  `Clean` while the lane matrix showed 39 error cells and all 1,117 prose cells
  unavailable. Changed the coarse summary wording to state its actual core
  extraction scope. The new corpus panel is still to be built.
- 2026-09-06: captured all 108 pages of QNB 2026Q1 solo into the new source
  representation; all typed text is conserved by the candidate lines. Source
  review of PDF page 47 found table rules made of thousands of raster dashes.
  Added candidate rule reconstruction and verified the resulting 23×3 mixed
  text table against the rendered PDF. Four independently annotated source
  cases pass; this is not a whole-document benchmark. Image/drawing review,
  table continuation and complete narrative semantics remain outstanding.
- 2026-09-06: Actions sample [34026793864](https://github.com/incesalim/Carthago/actions/runs/34026793864)
  preserved QNB 2026Q1 consolidated and solo: 218 pages, with original PDFs,
  evidence and candidate structure in eight R2 objects. Independently downloaded
  and verified the stored bytes and source accounting; the four annotated solo
  cases pass, while consolidated remains unannotated. CI exposed an unnecessary
  SDK import in offline storage tests; removed that dependency and tested the
  adapter with the SDK unavailable.
- 2026-09-06: identical replay [34027268957](https://github.com/incesalim/Carthago/actions/runs/34027268957)
  passed and left all ten stored objects unchanged, including ETag, byte count
  and modification time. Added a compact corpus catalog and private admin page
  viewer. Python-produced wire fixtures test exact page-byte compatibility with
  the Worker reader, plus dropped/changed pages, wrong sources and auth gating.
  Live deployment and broader source-format verification remain pending.
