# Paper-specific retrieval traps inspected in extracted text

These are verified textual hazards, not measured retriever failure rates. Check the rendered PDFs before using a numerical claim.

## Learned chunking versus RAG passage splitting
Dynamic Chunking v2, PDF p.1, describes data- and context-dependent segmentation learned jointly with H-Net. Its abstract discusses byte-level hierarchical sequence modeling, not fixed-size passages in a document store.

Trap question: “Does H-Net's reported improvement establish that our 420-word retrieval chunks outperform 180-word chunks?”
Expected: no such retrieval comparison is established. Matching the word 'chunking' is insufficient.

## Flattened equations and tables
Dynamic Chunking v2, PDF p.6, has the boundary probability equation. Extraction includes control characters and flattened numerator/denominator layout. Moshi v1, PDF p.8, flattens a multi-column hyperparameter table into a stream of values, although “Frame rate - 12.5 Hz” remains readable.

Trap question: “In Moshi's hyperparameter table, which training phase does each acoustic delay belong to?”
Expected: inspect the rendered table; do not infer column alignment solely from the flattened text.

## Other systems versus the paper's contribution
Moshi v1, PDF p.5, discusses AudioPaLM starting from pretrained PaLM and extending its vocabulary with semantic audio tokens. This describes related work, not Moshi's own initialization.

Trap question: “Does Moshi initialize from PaLM, as the AudioPaLM passage suggests?”
Expected: do not attribute AudioPaLM's design to Moshi. Moshi's Helium description is on PDF p.3 and further architecture details appear later.

Additional component trap: Moshi p.3 distinguishes Helium (text LM), Mimi (audio codec), and Moshi (dialogue framework). A mention of a Transformer is not evidence that these components are interchangeable with the original Transformer translation architecture.
