from relay.pipeline import canonical, validate

CHUNK = [{"id": "p:p1:c0", "text": "We suspect that for large values of dk, the self-attention sub-layer is theoret- ical. "
                                   "Our resulting model is the first real-time full-duplex model."}]


def draft(quote):
    return {"refused": False, "claims": [{"text": "t", "chunk_id": "p:p1:c0", "quote": quote}]}


def test_typographic_variants_are_accepted():
    assert validate(draft("the self\u2011attention sub\u2011layer is theoretical"), CHUNK)[0]      # non-breaking hyphen
    assert validate(draft("the first real\u2013time full\u2013duplex model"), CHUNK)[0]            # en dash
    assert validate(draft("we suspect that for large values of dk"), CHUNK)[0]                      # case
    assert validate(draft("sub-layer is theoret- ical. Our resulting model"), CHUNK)[0]             # source hyphenation verbatim


def test_still_strict_about_content():
    assert not validate(draft("the self-attention sub-layer is NOT theoretical at all here"), CHUNK)[0]   # altered words
    assert not validate(draft("We suspect that ... the first real-time full-duplex"), CHUNK)[0]            # spliced with ellipsis
    assert not validate(draft("for large values of dk, divided by sqrt dk times two"), CHUNK)[0]           # invented continuation
    assert not validate(draft("too short here"), CHUNK)[0]


def test_unknown_citation_still_rejected():
    d = draft("We suspect that for large values of dk")
    d["claims"][0]["chunk_id"] = "missing"
    assert not validate(d, CHUNK)[0]


def test_canonical_is_idempotent():
    t = "Self\u2011attention \u201cis\u201d fine"
    assert canonical(canonical(t)) == canonical(t)
