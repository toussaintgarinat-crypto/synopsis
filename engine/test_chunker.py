import chunker


def _entree(text, start, duration=2.0):
    return {"text": text, "start": start, "duration": duration}


def test_chunk_transcript_vide():
    assert chunker.chunk_transcript([]) == []


def test_chunk_transcript_tient_dans_un_seul_chunk():
    transcript = [_entree("Bonjour", 0.0), _entree("le monde", 2.0)]
    chunks = chunker.chunk_transcript(transcript, max_tokens=1000)
    assert len(chunks) == 1
    assert chunks[0]["start"] == 0.0
    assert chunks[0]["end"] == 4.0
    assert "Bonjour" in chunks[0]["text"]


def test_chunk_transcript_decoupe_si_trop_long():
    transcript = [_entree(f"mot numero {i} " * 20, float(i) * 3) for i in range(50)]
    chunks = chunker.chunk_transcript(transcript, max_tokens=200, overlap_tokens=20)
    assert len(chunks) > 1
    assert chunks[-1]["end"] >= transcript[-1]["start"]

    # Chaque chunk respecte le budget de tokens, sauf s'il ne contient qu'une
    # seule entrée déjà trop grosse à elle seule (garde-fou intentionnel de
    # l'algorithme : entrees_chunk non vide avant de couper).
    for c in chunks:
        entrees_dans_chunk = c["text"].count("\n") + 1
        assert c["tokens"] <= 200 or entrees_dans_chunk == 1, \
            f"Chunk avec {entrees_dans_chunk} entrées a {c['tokens']} tokens > 200"

    # Les chunks consécutifs se chevauchent réellement dans le temps.
    for i in range(len(chunks) - 1):
        assert chunks[i + 1]["start"] <= chunks[i]["end"], \
            f"Chunk {i+1} commence à {chunks[i+1]['start']}, mais chunk {i} finit à {chunks[i]['end']}"


def test_format_timestamp_minutes():
    assert chunker.format_timestamp(65) == "01:05"


def test_format_timestamp_heures():
    assert chunker.format_timestamp(3661) == "01:01:01"
