import warnings

import pytest

from howler.utils import str_utils


def test_named_constants():
    named_const_test = str_utils.NamedConstants("test", [("a", 1), ("B", 2), ("c", 3)])
    # success tests
    assert named_const_test.name_for_value(1) == "a"
    assert named_const_test.contains_value(1) is True
    assert named_const_test["a"] == 1
    assert named_const_test.c == 3
    # failure tests
    assert named_const_test.contains_value(4) is False
    with pytest.raises(KeyError):
        assert named_const_test.name_for_value(4) is None
        assert named_const_test["b"] == 2
        assert named_const_test.C == 3


def test_dotdump():
    result = str_utils.dotdump([1, 8, 22, 33, 66, 99, 126, 127, 1000])
    assert result == "...!Bc~.."


def test_safe_str():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        test_str = "helloÌ\x02Í\udcf9"
        test_bytes = b"hello\xc3\x8c\x02\xc3\x8d\udcf9"
        expected_result = "hello\xcc\\x02\xcd\\udcf9"

    assert str_utils.safe_str(test_bytes) == expected_result
    assert str_utils.safe_str(test_str) == expected_result


def test_safe_str_emoji():
    test_str = "Smile! \ud83d\ude00"
    test_bytes = b"Smile! \xf0\x9f\x98\x80"
    expected_result = "Smile! 😀"

    assert str_utils.safe_str(test_bytes) == expected_result
    assert str_utils.safe_str(test_str) == expected_result


def test_translate_str():
    teststr = "Стамболийски"
    encoded_test_str = teststr.encode("ISO-8859-5")
    result = str_utils.translate_str(encoded_test_str)
    assert result["language"] == "Bulgarian"
    assert result["encoding"] == "ISO-8859-5"
    result = str_utils.translate_str("abcdéfg")
    assert result["language"] == "unknown"
    assert result["encoding"] == "utf-8"


def test_remove_bidir_unicode_controls():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        test_str = "a\u202db\u202ac\u200ed\u200fe\u202efg\u202b"
    assert str_utils.remove_bidir_unicode_controls(test_str) == "abcdefg"

    other_test_str = "abcdéfg"
    assert str_utils.remove_bidir_unicode_controls(other_test_str) == "abcdéfg"


def test_wrap_bidir_unicode_string():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        test_str = "a\u202db\u202acde\u202efg\u202b"
        a = str_utils.wrap_bidir_unicode_string(test_str)
        assert a == "\u202aa\u202db\u202acde\u202efg\u202b\u202c\u202c\u202c\u202c\u202c"

        byte_str = b"\u202Dabcdefg"
        assert str_utils.wrap_bidir_unicode_string(byte_str) == b"\u202Dabcdefg"

        fail_search_str = "abcdefg"
        assert str_utils.wrap_bidir_unicode_string(fail_search_str) == "abcdefg"

        already_closed_str = "abc\u202adef\u202cg"
        assert str_utils.wrap_bidir_unicode_string(already_closed_str) == "\u202aabc\u202adef\u202cg\u202c"


def test_sanitize_lucene_query():
    assert str_utils.sanitize_lucene_query("APA3C - SENTINEL") == "APA3C \\- SENTINEL"
    assert (
        str_utils.sanitize_lucene_query('Test ^ weird " ~ query * string ? thing: \\ / a ( b ) c[ d ] e{ f} g-')
        == 'Test \\^ weird \\" \\~ query \\* string \\? thing\\: \\\\ \\/ a \\( b \\) c\\[ d \\] e\\{ f\\} g\\-'
    )
