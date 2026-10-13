from eval.run_eval import load_hard_cases
from kvkk_mask.known import fold
from kvkk_mask.names import tr_lower
from training.synth import EVAL_ONLY, LABELS, SynthGenerator, tokenize_with_spans


def test_tokens_and_tags_line_up():
    for tokens, tags in SynthGenerator(seed=1).sentences(2000):
        assert len(tokens) == len(tags)
        assert all(tag in LABELS for tag in tags)
        # An entity never starts with I-
        for prev, tag in zip(["O"] + tags, tags):
            if tag.startswith("I-"):
                assert prev[2:] == tag[2:]


def test_same_seed_same_data():
    assert SynthGenerator(seed=3).sentences(50) == SynthGenerator(seed=3).sentences(50)


def test_eval_names_never_appear_in_training_data():
    words = {fold(t) for tokens, _ in SynthGenerator(seed=0).sentences(20000) for t in tokens}
    assert not {fold(w) for w in EVAL_ONLY} & words


def test_eval_only_list_covers_unknown_hard_case_names():
    # Every hard-case person whose first name is not in the rule dictionary must be listed,
    # otherwise the model could simply memorise it.
    from kvkk_mask.names import first_names
    from kvkk_mask.recognizers import EntityType

    missing = set()
    for case in load_hard_cases():
        for e in case.gold:
            if e.type is EntityType.KISI:
                first = tr_lower(e.text.split()[0])
                if first not in first_names() and first not in EVAL_ONLY:
                    missing.add(first)
    assert missing == set()


def test_data_contains_the_hard_patterns():
    data = SynthGenerator(seed=0).sentences(5000)
    lower_names = attached_suffix = org_with_name = 0
    for tokens, tags in data:
        for token, tag in zip(tokens, tags):
            if tag == "B-PER" and token == tr_lower(token):
                lower_names += 1
            if tag == "B-ORG" and token in ("Deniz", "Umut", "Can", "Barış"):
                org_with_name += 1
        attached_suffix += any(t.endswith(("un", "in")) and g.endswith("PER") for t, g in zip(tokens, tags))
    assert lower_names > 300
    assert attached_suffix > 100
    assert org_with_name > 20


def test_tokenize_with_spans():
    text = "Kiracı Ayşe Yılmaz'ın A.Ş. ile 25.000 TL"
    tokens = tokenize_with_spans(text)
    assert [t for t, _, _ in tokens] == ["Kiracı", "Ayşe", "Yılmaz", "'", "ın", "A.Ş", ".", "ile", "25.000", "TL"]
    for token, start, end in tokens:
        assert text[start:end] == token
