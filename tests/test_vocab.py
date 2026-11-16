from actualizar import terms, fold


def test_fold_strips_accents():
    assert fold("Nación") == "Nacion"
    assert fold("júzguenlo").lower().startswith("juzg")


def test_terms_maps_spanish_phrase_and_stems():
    # vocab.py: "alto el fuego" -> ceasefire, recortado a 6 letras
    t = terms("Israel y Hamás pactan un alto el fuego en Gaza")
    assert "ceas" in t or "ceasef" in t or any(x.startswith("ceas") for x in t)
    assert "gaza" in t
    assert "israel" in t or "israe" in t


def test_terms_drops_stopwords_and_short_words():
    t = terms("The president of the country said it")
    assert "the" not in t
    assert "of" not in t
    # "president" / "said" / "country" after WORDS + stem 6
    assert any(x.startswith("presid") or x.startswith("said") or x.startswith("count") for x in t)


def test_years_in_range_are_not_kept_as_numbers():
    t = terms("Elections in 2026 and a figure of 15000")
    assert "#2026" not in t
    assert "#15000" in t or any(x == "#15000" for x in t)
