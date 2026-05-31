# pip-audit allowlist

Documented exceptions for `.github/workflows/security.yml` (`pip-audit --ignore-vuln …`).

| ID | Package | Rationale | Review |
| --- | --- | --- | --- |
| CVE-2026-45829 | chromadb | Pre-auth RCE in the **ChromaDB Python FastAPI server** when exposed to untrusted networks. No fixed release on PyPI (affects 1.5.x including latest). Aria uses `chromadb.HttpClient` against a pinned `chromadb/chroma` container on localhost/Docker only—not hosting the vulnerable API. | Re-check when Chroma ships a patched wheel; remove ignore and bump `chromadb` / Docker image. |
