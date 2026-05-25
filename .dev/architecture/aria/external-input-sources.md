Section:      external-input-sources
Version:      1.0.0
Last updated: 2026-05-24

```
Source:               Regulatory PDF files (local path or HTTP multipart upload)
Format:               application/pdf
Parser:               pdfplumber >=0.11
Trust level:          untrusted — user-supplied or corpus files; no malware scanning
Surfaces extracted:   per-page plain text, content SHA-256 hash, source path
Surfaces NOT extracted: embedded scripts, images/OCR text, digital signatures, attachments
Volume:               single-document CLI ingest; API limited by INGEST_MAX_BYTES / ARIA_MAX_INGEST_BODY_BYTES (default 12 MiB)
Sensitivity:          may contain regulatory text; parse errors fail closed per IngestionStatus
Owner module:         aria/ingestion/parsers/pdf_parser, aria/ingestion/pipeline
```

```
Source:               Regulatory HTML files (local path)
Format:               text/html, .htm
Parser:               BeautifulSoup4 >=4.12 with lxml >=5.3 backend
Trust level:          untrusted — boilerplate stripped via selector list, no HTML sanitization for XSS in stored text
Surfaces extracted:   title, section headings and body text, content hash
Surfaces NOT extracted: nav, footer, header, cookie banners, sidebar, script/style/noscript nodes
Volume:               same as PDF path via pipeline
Sensitivity:          same as PDF; external link URLs in HTML not followed
Owner module:         aria/ingestion/parsers/html_parser
```

```
Source:               POST /ingest/text and POST /ingest/file (API)
Format:               JSON text body or multipart file upload (PDF/HTML/text)
Parser:               chunk_text only — does not run full entity extraction pipeline
Trust level:          untrusted — authenticated when API_KEY set; body size capped
Surfaces extracted:   raw text → DocumentChunk list returned in response
Surfaces NOT extracted: no graph write, no vector index, no LLM entity extraction
Volume:               per-request, bounded by middleware body limit
Sensitivity:          chunk-only endpoint; lower blast radius than CLI full ingest
Owner module:         api/routers/ingest
```

```
Source:               POST /query naturalInput (natural language question)
Format:               JSON (ComplianceQueryRequest)
Parser:               Pydantic validation only; passed to retrieval + LLM
Trust level:          untrusted — user question drives vector search and LLM prompt
Surfaces extracted:   question string, optional regulation_id scope, top_k, use_graph_rag flag
Surfaces NOT extracted: no arbitrary Cypher; graph access via allow-listed query names only in retrieval layer
Volume:               interactive; top_k capped at 50
Sensitivity:          prompt injection surface into LLM; graph query names restricted
Owner module:         api/routers/query, aria/services/compliance_query
```

```
Source:               A2A POST /a2a/tasks (delegated agent tasks)
Format:               JSON TaskEnvelope
Parser:               Pydantic validation on server
Trust level:          partially trusted when A2A_SHARED_SECRET configured; otherwise open if route mounted
Surfaces extracted:   task_type, input_payload dict
Surfaces NOT extracted: no raw Cypher from payload; handler dispatches to registered agents
Volume:               low — in-process delegation demo
Sensitivity:          cross-agent payload injection; secret header optional
Owner module:         aria/protocols/a2a/server
```

```
Source:               MCP tool invocations (in-process, not network MCP transport)
Format:               Pydantic-validated tool inputs (query_name, parameters, query_text, etc.)
Parser:               aria/protocols/mcp/tools input schemas
Trust level:          partially trusted — callers are internal agents/orchestration
Surfaces extracted:   named query parameters, search text, regulation_id
Surfaces NOT extracted: arbitrary Cypher rejected — query_name must exist in QUERIES registry
Volume:               per orchestration step
Sensitivity:          parameter injection into parameterized Cypher only
Owner module:         aria/protocols/mcp/server
```
