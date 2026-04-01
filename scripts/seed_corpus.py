"""Load sample regulation documents into the ingestion pipeline.

Creates synthetic HTML regulation documents for development and testing
(avoids depending on external PDF downloads during development).

Run: python scripts/seed_corpus.py
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from aria.ingestion.pipeline import ingest_document, reset_ingestion_state

SAMPLE_REGULATIONS = {
    "gdpr_excerpt.html": """<!DOCTYPE html>
<html><head><title>GDPR - Excerpt</title></head><body>
<h1>Regulation (EU) 2016/679 — General Data Protection Regulation</h1>
<h2>Article 5 — Principles relating to processing of personal data</h2>
<p>Personal data shall be processed lawfully, fairly and in a transparent manner
in relation to the data subject. Personal data shall be collected for specified,
explicit and legitimate purposes and not further processed in a manner that is
incompatible with those purposes. Personal data shall be adequate, relevant and
limited to what is necessary in relation to the purposes for which they are processed.</p>
<h2>Article 17 — Right to erasure ('right to be forgotten')</h2>
<p>The data subject shall have the right to obtain from the controller the erasure
of personal data concerning him or her without undue delay and the controller shall
have the obligation to erase personal data without undue delay where the personal data
are no longer necessary in relation to the purposes for which they were collected.</p>
<h2>Article 35 — Data protection impact assessment</h2>
<p>Where a type of processing in particular using new technologies, and taking into
account the nature, scope, context and purposes of the processing, is likely to result
in a high risk to the rights and freedoms of natural persons, the controller shall,
prior to the processing, carry out an assessment of the impact of the envisaged
processing operations on the protection of personal data.</p>
</body></html>""",
    "eu_ai_act_excerpt.html": """<!DOCTYPE html>
<html><head><title>EU AI Act - Excerpt</title></head><body>
<h1>Regulation (EU) 2024/1689 — Artificial Intelligence Act</h1>
<h2>Article 6 — Classification rules for high-risk AI systems</h2>
<p>An AI system shall be considered high-risk where it is intended to be used as a
safety component of a product, or the AI system is itself a product, covered by
Union harmonisation legislation listed in Annex I. AI systems referred to in
Annex III shall be considered high-risk. The Commission is empowered to adopt
delegated acts to update the list in Annex III.</p>
<h2>Article 9 — Risk management system</h2>
<p>A risk management system shall be established, implemented, documented and
maintained in relation to high-risk AI systems. The risk management system shall
be understood as a continuous iterative process planned and run throughout the
entire lifecycle of a high-risk AI system, requiring regular systematic review
and updating. It shall comprise identification and analysis of the known and
the reasonably foreseeable risks that the high-risk AI system can pose.</p>
<h2>Article 52 — Transparency obligations for certain AI systems</h2>
<p>Providers shall ensure that AI systems intended to interact with natural persons
are designed and developed in such a way that the natural person is informed that
they are interacting with an AI system, unless this is obvious from the circumstances
and the context of use. This obligation shall not apply to AI systems authorised by
law to detect, prevent, investigate or prosecute criminal offences.</p>
</body></html>""",
}


async def main() -> None:
    reset_ingestion_state()

    with tempfile.TemporaryDirectory() as tmpdir:
        for filename, content in SAMPLE_REGULATIONS.items():
            path = Path(tmpdir) / filename
            path.write_text(content, encoding="utf-8")
            result = await ingest_document(path)
            print(f"{filename}: status={result.status}, chunks={result.chunks_produced}")


if __name__ == "__main__":
    asyncio.run(main())
