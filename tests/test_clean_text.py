"""Limpieza de HTML y texto que llega de los feeds."""
from actualizar import clean_text, trim, SUMMARY_MAX


def test_strips_simple_tags():
    assert clean_text("<p>Hola <b>mundo</b></p>") == "Hola mundo"


def test_unescapes_entities_then_strips_tags():
    raw = "Dice &lt;b&gt;hola&lt;/b&gt; y &amp; más"
    # primer unescape: <b>hola</b> y & más; se quitan las etiquetas
    assert "hola" in clean_text(raw)
    assert "<b>" not in clean_text(raw)
    assert "&" in clean_text(raw)


def test_script_payload_is_stripped_when_well_formed():
    raw = 'Antes <script>alert(1)</script> después'
    out = clean_text(raw)
    assert "alert(1)" in out  # el texto interior queda, no la etiqueta
    assert "<script>" not in out


def test_unclosed_tag_is_not_stripped():
    """TAG_RE exige '>' ; un tag sin cerrar sobrevive en el texto.
    Eso no es XSS si el front usa textContent, pero el HTML crudo queda."""
    raw = 'Título <img src=x onerror=alert(1) y sigue'
    out = clean_text(raw)
    assert "<img src=x onerror=alert(1)" in out


def test_trim_respects_limit_and_adds_ellipsis():
    long = "palabra " * 80
    out = trim(long, 40)
    assert len(out) <= 42  # recorte + elipsis
    assert out.endswith("…")


def test_empty_and_none():
    assert clean_text("") == ""
    assert clean_text(None) == ""
