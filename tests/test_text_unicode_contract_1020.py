from slang.stdlib.text import char_at_text, length_text, pad_left_text, pad_right_text, substring_text


def test_text_indices_count_unicode_codepoints():
    value = "кот"
    assert length_text(value) == 3.0
    assert char_at_text(value, 1) == "о"
    assert substring_text(value, 1, 3) == "от"


def test_padding_width_counts_unicode_codepoints():
    assert pad_left_text("я", 3, "猫") == "猫猫я"
    assert pad_right_text("я", 3, "猫") == "я猫猫"
