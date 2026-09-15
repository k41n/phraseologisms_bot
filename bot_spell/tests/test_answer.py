import answer


def test_case_and_yo_are_ignored():
    assert answer.is_correct("Не Дожидаясь", "не дожидаясь")
    assert answer.is_correct("ПО-ПРЕЖНЕМУ", "по-прежнему")
    assert answer.is_correct("нипочем", "нипочём")


def test_surrounding_noise_is_ignored():
    assert answer.is_correct("  «не двигаясь», ", "не двигаясь")
    assert answer.is_correct("по - прежнему", "по-прежнему")
    assert answer.is_correct("давным—давно", "давным-давно")


def test_the_separator_is_the_answer():
    assert not answer.is_correct("чем то", "чем-то")
    assert not answer.is_correct("чемто", "чем-то")
    assert not answer.is_correct("недожидаясь", "не дожидаясь")
    assert not answer.is_correct("не дожидаясь", "недожидаясь")


def test_empty_input_is_never_correct():
    assert not answer.is_correct("", "неизвестному")
    assert not answer.is_correct("???", "неизвестному")


def test_looks_like_answer():
    assert answer.looks_like_answer("не двигаясь")
    assert answer.looks_like_answer("ПО-ПРЕЖНЕМУ")
    assert not answer.looks_like_answer("")
    assert not answer.looks_like_answer("124")
    assert not answer.looks_like_answer("я не знаю как это пишется")
