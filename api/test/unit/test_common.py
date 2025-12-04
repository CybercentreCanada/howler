import os
from copy import deepcopy

import pytest
from baseconv import BASE62_ALPHABET

from howler.common import loader
from howler.common.classification import InvalidClassification
from howler.common.random_user import random_user
from howler.security.utils import get_password_hash, get_random_password, verify_password
from howler.utils.chunk import chunked_list
from howler.utils.dict_utils import flatten, get_recursive_delta, recursive_update, unflatten
from howler.utils.isotime import now_as_iso
from howler.utils.str_utils import safe_str, translate_str, truncate
from howler.utils.uid import LONG, MEDIUM, SHORT, TINY, get_id_from_data, get_random_id


def test_chunk():
    assert [[1, 2], [3, 4], [5, 6], [7, 8]] == chunked_list([1, 2, 3, 4, 5, 6, 7, 8], 2)


def test_classification():
    yml_config = os.path.join(os.path.dirname(os.path.dirname(__file__)), "classification.yml")
    cl_engine = loader.get_classification(yml_config=yml_config)

    u = "U//REL TO DEPTS"
    r = "R//GOD//REL TO G1"

    assert cl_engine.normalize_classification(r, long_format=True) == "RESTRICTED//ADMIN//ANY/GROUP 1"
    assert cl_engine.is_accessible(r, u)
    assert cl_engine.is_accessible(u, u)
    assert not cl_engine.is_accessible(u, r)
    assert cl_engine.min_classification(u, r) == "UNRESTRICTED//REL TO DEPARTMENT 1, DEPARTMENT 2"
    assert cl_engine.max_classification(u, r) == "RESTRICTED//ADMIN//ANY/GROUP 1"
    assert cl_engine.intersect_user_classification(u, r) == "UNRESTRICTED//ANY"
    assert cl_engine.normalize_classification("UNRESTRICTED//REL TO DEPARTMENT 2", long_format=False) == "U//REL TO D2"
    with pytest.raises(InvalidClassification):
        cl_engine.normalize_classification("D//BOB//REL TO SOUP")

    c1 = "U//REL TO D1"
    c2 = "U//REL TO D2"
    assert cl_engine.min_classification(c1, c2) == "UNRESTRICTED//REL TO DEPARTMENT 1, DEPARTMENT 2"
    assert cl_engine.intersect_user_classification(c1, c2) == "UNRESTRICTED"
    with pytest.raises(InvalidClassification):
        cl_engine.max_classification(c1, c2)

    dyn1 = "U//TEST"
    dyn2 = "U//GOD//TEST"
    dyn3 = "U//TEST2"
    assert not cl_engine.is_valid(dyn1)
    assert not cl_engine.is_valid(dyn2)
    assert cl_engine.normalize_classification(dyn1, long_format=False) == "U"
    assert cl_engine.normalize_classification(dyn2, long_format=False) == "U//ADM"
    cl_engine.dynamic_groups = True
    assert cl_engine.is_valid(dyn1)
    assert cl_engine.is_valid(dyn2)
    assert cl_engine.is_valid(dyn3)
    assert cl_engine.is_accessible(dyn2, dyn1)
    assert not cl_engine.is_accessible(dyn1, dyn2)
    assert not cl_engine.is_accessible(dyn3, dyn1)
    assert not cl_engine.is_accessible(dyn1, dyn3)
    assert cl_engine.intersect_user_classification(dyn1, dyn1) == "UNRESTRICTED//REL TO TEST"
    assert cl_engine.max_classification(dyn1, dyn2) == "UNRESTRICTED//ADMIN//REL TO TEST"
    assert cl_engine.normalize_classification(dyn1, long_format=True) == "UNRESTRICTED//REL TO TEST"
    assert cl_engine.normalize_classification(dyn1, long_format=False) == "U//REL TO TEST"


def test_dict_flatten():
    src = {"a": {"b": {"c": 1}}, "b": {"d": {2}}}

    flat_src = flatten(src)
    assert src == unflatten(flat_src)
    assert list(flat_src.keys()) == ["a.b.c", "b.d"]


def test_dict_recursive():
    src = {"a": {"b": {"c": 1}}, "b": {"d": 2}}
    add = {"a": {"d": 3, "b": {"c": 4}}}
    dest = recursive_update(deepcopy(src), add)
    assert dest["a"]["b"]["c"] == 4
    assert dest["a"]["d"] == 3
    assert dest["b"]["d"] == 2

    delta = get_recursive_delta(src, dest)
    assert add == delta


def test_random_user():
    assert len(random_user(digits=0, delimiter="_").split("_")) == 2
    assert len(random_user(digits=2, delimiter="_").split("_")) == 3
    assert int(random_user(digits=2, delimiter="-").split("-")[-1]) > -1


def test_safe_str():
    assert safe_str("hello") == "hello"
    assert safe_str("hello\x00") == "hello\\x00"
    assert safe_str("\xf1\x90\x80\x80") == "\xf1\x90\x80\x80"
    assert safe_str("\xc2\x90") == "\xc2\x90"
    assert safe_str("\xc1\x90") == "\xc1\x90"


def test_security():
    passwd = get_random_password()
    p_hash = get_password_hash(passwd)
    assert verify_password(passwd, p_hash)


def test_translate_str():
    assert translate_str(b"\xf1\x90\x80\x80\xc2\x90")["encoding"] == "utf-8"
    assert translate_str(b"fran\xc3\xa7ais \xc3\xa9l\xc3\xa8ve")["encoding"] == "utf-8"
    assert (
        translate_str(
            b"\x83G\x83\x93\x83R\x81[\x83f\x83B\x83\x93\x83O\x82" b"\xcd\x93\xef\x82\xb5\x82\xad\x82\xc8\x82\xa2"
        )["language"]
        == "Japanese"
    )


def test_truncate():
    assert truncate(b"blah") == "blah"
    assert truncate(b"blah", 10) == "blah"
    assert truncate(b"blahblahblahblah", 10) == "blahblahbl..."


def test_uid():
    test_data = "test" * 1000
    rid = get_random_id()
    id_test = get_id_from_data(test_data)
    id_test_l = get_id_from_data(test_data, length=LONG)
    id_test_m = get_id_from_data(test_data, length=MEDIUM)
    id_test_s = get_id_from_data(test_data, length=SHORT)
    id_test_t = get_id_from_data(test_data, length=TINY)
    assert 23 > len(rid) >= 20
    assert 23 > len(id_test) >= 20
    assert 44 > len(id_test_l) >= 41
    assert 23 > len(id_test_m) >= 20
    assert 13 > len(id_test_s) >= 10
    assert 8 > len(id_test_t) >= 5
    assert id_test == id_test_m
    for c_id in [rid, id_test, id_test_l, id_test_m, id_test_s, id_test_t]:
        for x in c_id:
            assert x in BASE62_ALPHABET


def test_now_as_iso():
    assert now_as_iso().endswith("Z")
