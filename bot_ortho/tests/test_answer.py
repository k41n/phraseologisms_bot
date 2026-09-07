import answer


def test_normalise_ignores_order_and_separators():
    assert answer.normalise("4, 2 и 1") == "124"
    assert answer.normalise("124") == "124"
    assert answer.normalise("421") == "124"


def test_normalise_dedupes():
    assert answer.normalise("1 1 3") == "13"


def test_is_correct():
    assert answer.is_correct("241", "124")
    assert answer.is_correct("1,2,4", "124")
    assert not answer.is_correct("12", "124")
    assert not answer.is_correct("", "124")
    assert not answer.is_correct("не знаю", "124")


def test_looks_like_answer():
    assert answer.looks_like_answer("124")
    assert answer.looks_like_answer("1, 2")
    assert not answer.looks_like_answer("не знаю")
    assert not answer.looks_like_answer("")
    assert not answer.looks_like_answer("привет 12")


def test_word_answers_ignore_case_yo_and_separators():
    assert answer.normalise_word("Приволье, приуныть") == "привольеприуныть"
    assert answer.is_correct("подъём объявление", "подъемобъявление", "word")
    assert answer.is_correct("Бреют", "бреют", "word")
    assert not answer.is_correct("бреет", "бреют", "word")
    assert not answer.is_correct("", "бреют", "word")


def test_looks_like_answer_by_kind():
    assert answer.looks_like_answer("бреют", "word")
    assert not answer.looks_like_answer("124", "word")
    assert not answer.looks_like_answer("бреют", "rows")


def test_letters_keep_order_and_ignore_separators():
    assert answer.normalise_letters("Ь, ь, Ъ") == "ььъ"
    assert answer.is_correct("ь, ь, ъ", "ь, ь, ъ", "letters")
    assert answer.is_correct("ььъ", "ь, ь, ъ", "letters")
    assert answer.is_correct("Е,Е,Е", "ё, ё, ё", "letters")
    assert not answer.is_correct("ь, ъ, ь", "ь, ь, ъ", "letters")
    assert not answer.is_correct("ь, ь", "ь, ь, ъ", "letters")
    assert not answer.is_correct("", "ь, ь, ъ", "letters")


def test_looks_like_letters():
    assert answer.looks_like_answer("а, а, а", "letters")
    assert answer.looks_like_answer("ааа", "letters")
    assert not answer.looks_like_answer("не знаю", "letters")
    assert not answer.looks_like_answer("124", "letters")
    assert not answer.looks_like_answer("", "letters")
