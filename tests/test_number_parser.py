import pytest

from src.number_parser import en_amounts, en_digit_runs, en_times, hi_spans, parse_hi_amount


@pytest.mark.parametrize("words,value", [
    ("पाँच लाख", 500_000),
    ("पांच करोड़", 50_000_000),            # anusvara spelling variant
    ("पच्चीस हज़ार", 25_000),
    ("पच्चीस हजार", 25_000),               # without nukta
    ("डेढ़ करोड़", 15_000_000),
    ("ढाई लाख", 250_000),
    ("साढ़े बारह लाख", 1_250_000),
    ("सवा दो लाख", 225_000),
    ("पौने तीन सौ", 275),
    ("एक लाख पचास हज़ार", 150_000),
    ("दो करोड़ पचास लाख", 25_000_000),
    ("तीन सौ", 300),
    ("निन्यानवे", 99),
    ("सैंतालीस", 47),
])
def test_hindi_amounts(words, value):
    assert parse_hi_amount(words.split()) == pytest.approx(value)


def test_hindi_amount_rejects_non_numbers():
    assert parse_hi_amount(["पाँच", "रुपये"]) is None
    assert parse_hi_amount(["साढ़े"]) is None      # dangling fraction modifier


def test_hindi_spans_digits_vs_amounts():
    spans = hi_spans("नंबर है नौ आठ सात छह, पाँच चार। और बीस हज़ार रुपये")
    assert spans[0] == {"kind": "digits", "start": 2, "end": 8, "value": "987654"}
    assert spans[1]["kind"] == "amount" and spans[1]["value"] == 20_000


def test_hindi_digit_run_stops_at_sentence_end():
    spans = hi_spans("दो एक शून्य। एक मिनट")
    assert spans[0]["value"] == "210"


@pytest.mark.parametrize("text,value", [
    ("five crore rupees", 50_000_000),
    ("Rs 5 crore", 50_000_000),
    ("Rs. 5 cr", 50_000_000),
    ("₹5,00,00,000", 50_000_000),
    ("50,000,000 rupees", 50_000_000),
    ("50 million", 50_000_000),
    ("one and a half crore", 15_000_000),
    ("twelve and a half lakh", 1_250_000),
    ("12.5 lakhs", 1_250_000),
    ("one lakh fifty thousand", 150_000),
    ("Twenty-five thousand rupees", 25_000),
    ("Rs 25k", 25_000),
    ("two thousand five hundred", 2_500),
    ("one hundred and five", 105),
])
def test_english_amounts(text, value):
    assert value in [pytest.approx(v) for v in en_amounts(text)]


def test_english_digit_strings_are_not_amounts():
    # 'four four two seven' must not be summed into 17
    assert 17 not in en_amounts("account four four two seven")
    assert en_amounts("account four four two seven") == []


@pytest.mark.parametrize("text,digits", [
    ("nine eight seven six, five four three, two one eight", "9876543218"),
    ("98765-43218", "9876543218"),
    ("98765 43218", "9876543218"),
    ("double four two seven, one nine, six three", "44271963"),
    ("nine eight oh one", "9801"),
])
def test_digit_runs(text, digits):
    assert digits in en_digit_runs(text)


def test_digit_run_breaks_at_sentence_end():
    runs = en_digit_runs("two one zero. One moment")
    assert "210" not in runs and all("2101" not in r for r in runs)


@pytest.mark.parametrize("text,t", [
    ("at four thirty", "4:30"), ("at 4:30", "4:30"), ("half past four", "4:30"),
    ("quarter to five", "4:45"), ("four o'clock", "4:00"), ("at four", "4:00"),
])
def test_times(text, t):
    assert t in en_times(text)


def test_four_thirty_is_not_four_oclock():
    assert "4:00" not in en_times("The meeting is at four thirty.")
