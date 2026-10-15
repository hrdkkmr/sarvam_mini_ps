from src.entity_checker import check_entity


def ent(type_, **expected):
    return {"id": "e", "type": type_, "expected": expected}


NEG_PAY = ent("negation", predicates=["make", "made", "pay", "paid"], polarity="negative")


def test_negation_present():
    assert check_entity(NEG_PAY, "I did not make that payment.").passed
    assert check_entity(NEG_PAY, "I didn't pay.").passed
    assert check_entity(NEG_PAY, "I never paid it.").passed


def test_negation_dropped():
    r = check_entity(NEG_PAY, "I made that payment.")
    assert not r.passed and r.reason == "polarity_wrong"


def test_negation_scope_stops_at_clause_break():
    # the 'not' belongs to the first clause, the payment clause is affirmative
    assert not check_entity(NEG_PAY, "It is not my card, but I made the payment.").passed


def test_not_only_is_not_negation():
    assert not check_entity(NEG_PAY, "Not only did I make the payment.").passed


def test_missing_predicate_fails_not_passes():
    r = check_entity(NEG_PAY, "Something else entirely.")
    assert not r.passed and r.reason == "predicate_not_found"


def test_affirmative_control():
    e = ent("negation", predicates=["need"], polarity="affirmative")
    assert check_entity(e, "I need it.").passed
    assert not check_entity(e, "I don't need it.").passed


def test_known_limitation_negation_after_predicate():
    # documented failure: 'made no such payment' is negative but the cue follows the verb
    assert not check_entity(NEG_PAY, "I made no such payment.").passed


CORR = ent("correction", kind="amount", final=50_000_000, abandoned=500_000)


def test_correction_final_only():
    assert check_entity(CORR, "The amount is five crore rupees.").passed


def test_correction_abandoned_as_fact():
    r = check_entity(CORR, "The amount is five lakh rupees.")
    assert not r.passed and r.reason == "final_missing"
    r = check_entity(CORR, "It was five lakh. Later it became five crore.")
    assert not r.passed and r.reason == "abandoned_asserted"


def test_correction_explicitly_rejected_is_ok():
    assert check_entity(CORR, "It is five crore, not five lakh.").passed


def test_correction_literal_mode_allows_disfluency():
    text = "Amount about five lakh, no no, sorry, five crore rupees."
    assert not check_entity(CORR, text, "fluent").passed
    assert check_entity(CORR, text, "literal").passed


def test_phone_correction():
    e = ent("correction", kind="digits", final="9876543218", abandoned="9876543210")
    good = "Nine eight seven six, five four three, two one eight. One moment, it is eight."
    bad = "Nine eight seven six, five four three, two one zero. One moment, it is eight. " \
          "So it is nine eight seven six five four three two one eight."
    assert check_entity(e, good).passed
    assert not check_entity(e, bad).passed


def test_names_and_acronyms():
    e = ent("org", variants=["SBI"])
    assert check_entity(e, "at S.B.I. today").passed
    assert check_entity(e, "at S B I today").passed
    assert not check_entity(e, "at the bank").passed
    p = ent("person", variants=["Rahul Verma"])
    assert not check_entity(p, "Rahul Varma").passed


def test_unknown_amount_is_not_marked_correct():
    e = ent("amount", value=150_000)
    assert not check_entity(e, "half a lakh and some more").passed
