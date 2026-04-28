import json
import os

import pytest

from howler.common.classification import InvalidClassification
from howler.common.exceptions import HowlerException
from howler.odm import (
    UUID,
    Classification,
    Compound,
    Domain,
    Enum,
    FlattenedObject,
    Integer,
    KeyMaskException,
    Keyword,
    List,
    Mapping,
    Model,
    construct_safe,
    flat_to_nested,
    model,
)
from howler.odm.models.ecs.client import Client
from howler.odm.models.ecs.email import Email


class CatError(Exception):
    """A unique exception class."""

    pass


def test_index_defaults():
    @model()
    class Test1(Model):
        default = Keyword()
        indexed = Keyword(index=True)
        not_indexed = Keyword(index=False)

    fields = dict(Test1.fields())
    assert fields["default"].index is None
    assert fields["indexed"].index is True
    assert fields["not_indexed"].index is False

    @model(index=True)
    class Test2(Model):
        default = Keyword()
        indexed = Keyword(index=True)
        not_indexed = Keyword(index=False)

    fields = dict(Test2.fields())
    assert fields["default"].index is True
    assert fields["indexed"].index is True
    assert fields["not_indexed"].index is False

    @model(index=False)
    class Test3(Model):
        default = Keyword()
        indexed = Keyword(index=True)
        not_indexed = Keyword(index=False)

    fields = dict(Test3.fields())
    assert fields["default"].index is False
    assert fields["indexed"].index is True
    assert fields["not_indexed"].index is False


def test_compound_index_defaults():
    @model()
    class SubModel(Model):
        default = Keyword()
        indexed = Keyword(index=True)
        not_indexed = Keyword(index=False)

    @model()
    class Test1(Model):
        default = Compound(SubModel)
        indexed = Compound(SubModel, index=True)
        not_indexed = Compound(SubModel, index=False)

    fields = Test1.flat_fields()
    assert fields["default.default"].index is None
    assert fields["default.indexed"].index is True
    assert fields["default.not_indexed"].index is False

    fields = Test1.flat_fields()
    assert fields["indexed.default"].index is True
    assert fields["indexed.indexed"].index is True
    assert fields["indexed.not_indexed"].index is False

    fields = Test1.flat_fields()
    assert fields["not_indexed.default"].index is False
    assert fields["not_indexed.indexed"].index is True
    assert fields["not_indexed.not_indexed"].index is False


def test_creation():
    @model()
    class Test(Model):
        first = Keyword()
        second = Integer()

    instance = Test(dict(first="abc", second=567))

    assert instance.first == "abc"
    assert instance.second == 567

    instance.first = "xyz"
    instance.second = 123

    assert instance.first == "xyz"
    assert instance.second == 123


def test_type_validation():
    @model()
    class Test(Model):
        first = Keyword()
        second = Integer()

    with pytest.raises(ValueError):
        Test(dict(cats=123))

    instance = Test(dict(first="abc", second=567))

    with pytest.raises(ValueError):
        instance.second = "cats"

    with pytest.raises(ValueError):
        instance.first = b"abc"


# noinspection PyPropertyAccess
def test_setters():
    # noinspection PyPropertyDefinition
    @model()
    class Test(Model):
        first = Keyword()

        @first.setter
        def first(self, value):
            assert isinstance(value, str)
            if value.startswith("cat"):
                raise CatError()
            return value

    instance = Test(dict(first="abc"))
    assert instance.first == "abc"

    instance.first = "xyz"
    assert instance.first == "xyz"

    instance.first = 123
    assert instance.first == "123"

    with pytest.raises(CatError):
        instance.first = "cats"


def test_setters_side_effects():
    """Test setters that change other field values."""

    # noinspection PyPropertyAccess, PyPropertyDefinition
    @model()
    class Test(Model):
        a = Integer()
        b = Integer()
        best = Integer()

        @a.setter
        def a(self, value):
            self.best = min(self.b, value)
            return value

        @b.setter
        def b(self, value):
            self.best = min(self.a, value)
            return value

    instance = Test(dict(a=-100, b=10, best=-100))

    instance.a = 50
    assert instance.best == 10
    instance.b = -10
    assert instance.best == -10


# noinspection PyPropertyAccess
def test_getters():
    # noinspection PyPropertyDefinition
    @model()
    class Test(Model):
        first = Integer()

        @first.getter
        def first(self, value):
            return value if value >= 1 else 100

    instance = Test(dict(first=10))
    assert instance.first == 10

    instance.first = -1
    assert instance.first == 100

    instance.first = 500
    assert instance.first == 500


def test_create_compound():
    @model()
    class TestCompound(Model):
        key = Keyword()
        value = Keyword()

    @model()
    class Test(Model):
        first = Compound(TestCompound)

    test = Test({"first": {"key": "a", "value": "b"}})
    assert test.first.key == "a"
    test.first.key = 100
    assert test.first.key == "100"


def test_json():
    @model()
    class Inner(Model):
        number = Integer()
        value = Keyword()

    @model()
    class Test(Model):
        a = Compound(Inner)
        b = Integer()

    a = Test(dict(b=10, a={"number": 499, "value": "cats"}))
    b = Test(json.loads(a.json()))

    assert b.b == 10
    assert b.a.number == 499
    assert b.a.value == "cats"


def test_create_list():
    @model()
    class Test(Model):
        values = List(Integer())

    _ = Test(dict(values=[]))
    test = Test(dict(values=[0, 100]))

    with pytest.raises(ValueError):
        Test(dict(values=["bugs"]))

    with pytest.raises(ValueError):
        Test(dict(values="bugs"))

    assert test.values[0] == 0
    assert test.values[1] == 100

    test.values.append(10)
    assert len(test.values) == 3

    with pytest.raises(ValueError):
        test.values.append("cats")

    with pytest.raises(ValueError):
        test.values[0] = "cats"

    test.values += range(5)
    assert len(test.values) == 8

    test.values.extend(range(2))
    assert len(test.values) == 10

    test.values.insert(0, -100)
    assert len(test.values) == 11
    assert test.values[0] == -100

    test.values[0:5] = range(5)
    assert len(test.values) == 11
    for ii in range(5):
        assert test.values[ii] == ii


def test_create_list_compounds():
    @model()
    class Entry(Model):
        value = Integer()
        key = Keyword()

    @model()
    class Test(Model):
        values = List(Compound(Entry))

    fields = Test.fields()
    assert len(fields) == 1
    fields = Test.flat_fields()
    assert len(fields) == 2

    _ = Test(dict(values=[]))
    test = Test({"values": [{"key": "cat", "value": 0}, {"key": "rat", "value": 100}]})

    with pytest.raises(TypeError):
        Test(values=["bugs"])  # type: ignore[call-arg]

    assert test.values[0].value == 0
    assert test.values[1].value == 100

    test.values.append({"key": "bat", "value": 50})

    assert len(test.values) == 3

    with pytest.raises(TypeError):
        test.values.append(1000)

    with pytest.raises(TypeError):
        test.values[0] = "cats"

    with pytest.raises(ValueError):
        test.values[0] = {"key": "bat", "value": 50, "extra": 1000}

    test.values[0].key = "dog"


def test_defaults():
    @model()
    class InnerA(Model):
        number = Integer(default=10)
        value = Keyword()

    @model()
    class InnerB(Model):
        number = Integer()
        value = Keyword()

    @model()
    class Test(Model):
        a = Compound(InnerA)
        b = Compound(InnerB)
        c = Compound(InnerB, default={"number": 99, "value": "yellow"})
        x = Integer()
        y = Integer(default=-1)

    # Build a model with missing data found in the defaults
    test = Test({"a": {"value": "red"}, "b": {"number": -100, "value": "blue"}, "x": -55})

    assert test.a.number == 10
    assert test.a.value == "red"
    assert test.b.number == -100
    assert test.b.value == "blue"
    assert test.c.number == 99
    assert test.c.value == "yellow"
    assert test.x == -55
    assert test.y == -1


def test_field_masking():
    @model()
    class Test(Model):
        a = Integer()
        b = Integer()

    test = Test(dict(a=10), mask=["a"])

    assert test.a == 10

    with pytest.raises(KeyMaskException):
        _ = test.b

    with pytest.raises(KeyMaskException):
        test.b = 100


def test_sub_field_masking():
    @model()
    class Inner(Model):
        a = Integer()
        b = Integer()

    @model()
    class Test(Model):
        a = Compound(Inner)
        b = Compound(Inner)

    test = Test(dict(a=dict(a=10), b=dict(b=10)), mask=["a.a", "b.b"])

    assert test.a.a == 10

    with pytest.raises(KeyMaskException):
        _ = test.b.a

    with pytest.raises(KeyMaskException):
        test.a.b = 100


def test_mapping():
    @model()
    class Test(Model):
        a = Mapping(Integer(), default={}, index=True, store=True)

    test = Test({})

    assert len(test.a) == 0

    with pytest.raises(KeyError):
        _ = test.a["abc"]

    with pytest.raises(KeyError):
        test.a["abc.abc.abc"] = None

    with pytest.raises(KeyError):
        test.a["4abc"] = None

    with pytest.raises(KeyError):
        test.a["ABC"] = None

    with pytest.raises(KeyError):
        test.a["a b"] = None

    test.a["cat"] = 10
    test.a["dog"] = -100

    assert len(test.a) == 2
    assert test.a["dog"] == -100

    with pytest.raises(ValueError):
        test.a["red"] = "can"

    test = Test({"a": {"walk": 100}})
    assert len(test.a) == 1
    assert test.a["walk"] == 100


def test_non_indexed_mapping():
    @model()
    class Test(Model):
        a = Mapping(Integer(), default={}, index=False, store=False)

    test = Test({})
    assert len(test.a) == 0
    with pytest.raises(KeyError):
        _ = test.a["abc"]

    with pytest.raises(KeyError):
        test.a["abc.abc.abc"] = None

    test.a["4abc"] = 1
    test.a["ABC"] = 1
    test.a["a b"] = 1
    test.a["cat"] = 10
    test.a["dog"] = -100

    assert len(test.a) == 5
    assert test.a["dog"] == -100

    with pytest.raises(ValueError):
        test.a["red"] = "can"

    test = Test({"a": {"walk": 100}})
    assert len(test.a) == 1
    assert test.a["walk"] == 100


def test_flattened_object():
    @model()
    class Test(Model):
        a = FlattenedObject(default={}, index=True, store=True)

    test = Test()

    assert len(test.a) == 0

    with pytest.raises(KeyError):
        _ = test.a["abc"]

    with pytest.raises(KeyError):
        test.a["4abc"] = "hello"

    with pytest.raises(KeyError):
        test.a["ABC"] = "hello"

    with pytest.raises(KeyError):
        test.a["a b"] = "hello"

    test.a["abc"] = 1
    test.a["abc.abc.abc"] = "hello"
    test.a["cat"] = "cat"
    test.a["dog"] = "dog"

    assert len(test.a) == 4
    assert test.a["dog"] == "dog"
    assert test.a["abc"] == "1"

    test = Test({"a": {"walk": 100}})
    assert len(test.a) == 1
    assert test.a["walk"] == "100"


def test_classification():
    yml_config = os.path.join(os.path.dirname(os.path.dirname(__file__)), "classification.yml")

    @model(index=True, store=True)
    class ClassificationTest(Model):
        cl = Classification(default="UNRESTRICTED", yml_config=yml_config)

    u = ClassificationTest({"cl": "U//REL TO D1, D2"})
    r = ClassificationTest({"cl": "R//GOD//G1"})

    assert str(r.cl) == "RESTRICTED//ADMIN//ANY/GROUP 1"

    assert u.cl < r.cl
    assert u.cl <= u.cl
    assert u.cl >= u.cl
    assert not u.cl >= r.cl
    assert not u.cl > u.cl
    assert u.cl == u.cl
    assert not u.cl != u.cl
    assert r.cl > u.cl
    assert not u.cl > r.cl
    assert str(u.cl.min(r.cl)) == "UNRESTRICTED//REL TO DEPARTMENT 1, DEPARTMENT 2"
    assert str(u.cl.max(r.cl)) == "RESTRICTED//ADMIN//ANY/GROUP 1"
    assert str(u.cl.intersect(r.cl)) == "UNRESTRICTED//ANY"
    assert str(r.cl.small()) == "R//ADM//ANY/G1"

    with pytest.raises(InvalidClassification):
        _ = ClassificationTest({"cl": "D//BOB//REL TO SOUP"})

    c1 = ClassificationTest({"cl": "U//REL TO D1"})
    c2 = ClassificationTest({"cl": "U//REL TO D2"})
    assert str(c1.cl.min(c2.cl)) == "UNRESTRICTED//REL TO DEPARTMENT 1, DEPARTMENT 2"
    assert str(c1.cl.intersect(c2.cl)) == "UNRESTRICTED"
    with pytest.raises(InvalidClassification):
        _ = c1.cl.max(c2.cl)


def test_enum():
    @model(index=True, store=True)
    class EnumTest(Model):
        enum = Enum(values=["magic", "data", "elasticsearch"])

    et = EnumTest({"enum": "magic"})
    assert et.enum == "magic"

    et.enum = "magic"
    assert et.enum == "magic"
    et.enum = "data"
    assert et.enum == "data"
    et.enum = "elasticsearch"
    assert et.enum == "elasticsearch"

    with pytest.raises(ValueError):
        et.enum = "bob"

    with pytest.raises(ValueError):
        et.enum = "mysql"

    with pytest.raises(ValueError):
        et.enum = 1

    with pytest.raises(TypeError):
        et.enum = ["a"]

    with pytest.raises(ValueError):
        et.enum = True


# noinspection PyUnusedLocal
def test_banned_keys():
    with pytest.raises(ValueError):

        @model(index=True, store=True)
        class BannedTest(Model):
            _1 = Integer()

    with pytest.raises(ValueError):

        @model(index=True, store=True)
        class BannedTest2(Model):
            _id = Integer()

    with pytest.raises(ValueError):

        @model(index=True, store=True)
        class BannedTest3(Model):
            ALL = Integer()


def test_named_item_access():
    @model()
    class Inner(Model):
        a = Integer()
        b = Integer()

    @model()
    class Test(Model):
        a = Compound(Inner)
        b = Integer()

    test = Test(dict(a=dict(a=10, b=100), b=99))

    assert test.a["a"] == 10
    assert test["a"].a == 10
    assert test.a.a == 10
    assert test["a"]["a"] == 10
    test.a["a"] = 1
    assert test.a["a"] == 1
    assert test["a"].a == 1
    assert test.a.a == 1
    assert test["a"]["a"] == 1
    test["a"].a = -1
    assert test.a["a"] == -1
    assert test["a"].a == -1
    assert test.a.a == -1
    assert test["a"]["a"] == -1

    with pytest.raises(KeyError):
        _ = test["x"]

    with pytest.raises(KeyError):
        test["x"] = 100

    assert test["a"] == {"a": -1, "b": 100}


def test_uuid():
    @model()
    class Test(Model):
        uuid = UUID()

    a = Test()
    b = Test()
    assert a.uuid != "" and a.uuid is not None
    assert a.uuid != b.uuid

    b.uuid = "123abc"
    c = Test({"uuid": "abc123"})

    assert a.uuid != b.uuid and b.uuid != c.uuid
    assert b.uuid == "123abc"
    assert c.uuid == "abc123"


def test_name_injection():
    @model()
    class A(Model):
        fast = Integer(default=1)
        slow = Keyword(default="abc")
        flags = List(Keyword(), default=["cat-snack"])

    @model()
    class B(Model):
        speed = Compound(A, default={})

    a = A()
    fields = a.fields()
    assert fields["fast"].name == "fast"
    assert fields["slow"].name == "slow"
    assert fields["flags"].name == "flags"

    fields = a.flat_fields()
    assert fields["fast"].name == "fast"
    assert fields["slow"].name == "slow"

    b = B()
    fields = b.fields()
    assert fields["speed"].name == "speed"

    fields = b.flat_fields()
    assert fields["speed.fast"].name == "fast"
    assert fields["speed.slow"].name == "slow"


def test_construct_safe():
    @model()
    class Flag(Model):
        uuid = UUID()
        name = Keyword()
        fans = List(Integer(), default=[])

    @model()
    class A(Model):
        fast = Integer(default=1)
        slow = Keyword(default="abc")
        count = List(Integer())

    @model()
    class B(Model):
        speed = Compound(A, default={})
        flags = List(Compound(Flag))

    out, dropped = construct_safe(
        B,
        {
            "speed": {"fast": "abc", "count": ["100", 100, "hundred", "9dy"]},
            "flags": [
                "abc",
                {"uuid": "bad"},
                {"name": "good"},
                {"name": "some-good", "fans": [1, "99", "many"]},
            ],
            "cats": "red",
        },
    )

    assert out.speed.fast == 1
    assert out.speed.slow == "abc"
    assert out.speed.count == [100, 100]
    assert len(out.flags) == 2
    assert out.flags[0].name == "good"
    assert out.flags[0].uuid
    assert len(out.flags[0].fans) == 0
    assert out.flags[1].name == "some-good"
    assert out.flags[1].uuid
    assert set(out.flags[1].fans) == {1, 99}

    assert dropped["cats"] == "red"
    assert dropped["speed"]["fast"] == "abc"
    assert set(dropped["speed"]["count"]) == {"hundred", "9dy"}
    assert len(dropped["flags"]) == 3
    assert dropped["flags"][0] == "abc"
    assert dropped["flags"][1]["uuid"] == "bad"
    assert dropped["flags"][2]["fans"] == ["many"]


def test_model_equal():
    @model()
    class Inner(Model):
        a = Integer()
        b = Integer()

    @model()
    class Test(Model):
        a = Compound(Inner)
        b = Integer()

    a = Test(dict(a=dict(a=10, b=5), b=99))
    assert a == dict(a=dict(a=10, b=5), b=99)
    assert a != dict(a=dict(a=0, b=5), b=99)
    assert a != dict(a=dict(a=10, b=5), b=0)
    assert a != dict(a=dict(a=10, b=5))
    assert a != []
    assert a != 99


def test_flat_to_nested():
    assert flat_to_nested({}) == {}
    assert flat_to_nested({"a.b.c": None}) == {"a": {"b": {"c": None}}}


def test_ip():
    ipv6 = "2002:efa3:a345:9310:4adc:aef6:8597:0020"
    ipv4 = "127.0.0.1"

    data = Client({"ip": ipv6})

    assert data.ip == ipv6

    data = Client({"ip": ipv4})

    assert data.ip == ipv4


def test_list_of_compounds():
    validated = Email(
        {
            "attachments.file.hash.sha256": [
                "a59d30df946cc54923a3f39401e489dab1e25c7eeec257ca662abce6a17dd894",
                "a59d30df946cc54923a3f39401e489dab1f25c7eeec257ca662abce6a17dd894",
            ],
            "attachments.file.hash.sha1": [
                "c4a9b2d23e35f3f98d4117c3285f1a9db4ff0ced",
                "c4a9b2d23e35f3f98d4127c3285f1a9db4ff0ced",
            ],
        }
    )

    assert len(validated.attachments) == 2

    assert (
        validated.attachments[0].file.hash.sha256 == "a59d30df946cc54923a3f39401e489dab1e25c7eeec257ca662abce6a17dd894"
    )
    assert (
        validated.attachments[1].file.hash.sha256 == "a59d30df946cc54923a3f39401e489dab1f25c7eeec257ca662abce6a17dd894"
    )

    assert validated.attachments[0].file.hash.sha1 == "c4a9b2d23e35f3f98d4117c3285f1a9db4ff0ced"
    assert validated.attachments[1].file.hash.sha1 == "c4a9b2d23e35f3f98d4127c3285f1a9db4ff0ced"

    assert (
        len(
            Email(
                {"attachments.file.hash.sha256": "a59d30df946cc54923a3f39401e489dab1e25c7eeec257ca662abce6a17dd894"}
            ).attachments
        )
        == 1
    )

    assert (
        validated.attachments[0].file.hash.sha256 == "a59d30df946cc54923a3f39401e489dab1e25c7eeec257ca662abce6a17dd894"
    )

    with pytest.raises(HowlerException):
        Email(
            {
                "attachments.file.hash.sha256": [
                    "a59d30df946cc54923a3f39401e489dab1e25c7eeec257ca662abce6a17dd894",
                    "a59d30df946cc54923a3f39401e489dab1f25c7eeec257ca662abce6a17dd894",
                ],
                "attachments.file.hash.sha1": [
                    "c4a9b2d23e35f3f98d4117c3285f1a9db4ff0ced",
                ],
            }
        )


def test_domain():
    @model()
    class Test(Model):
        domain = Domain(strict=False)
        strict_domain = Domain(optional=True)

    Test({"domain": "google.com", "strict_domain": "google.com"})
    Test({"domain": "foo.com", "strict_domain": "foo.com"})
    Test({"domain": "foo", "strict_domain": "foo.com"})
    Test({"domain": "foo.bar.baz-qux", "strict_domain": "foo.bar.baz-qux"})

    with pytest.raises(HowlerException):
        Test({"domain": "invalid!type of text!!!.com"})

    with pytest.raises(HowlerException):
        Test({"domain": "piotato."})

    with pytest.raises(HowlerException):
        Test({"domain": "foo", "strict_domain": "foo"})


def test_flat_fields_show_compound_list_of_compound():
    """flat_fields(show_compound=True) should include the compound child type for List[Compound] fields."""

    @model()
    class Inner(Model):
        name = Keyword()
        value = Integer()

    @model()
    class Outer(Model):
        items = List(Compound(Inner))
        label = Keyword()

    flat = Outer.flat_fields(show_compound=True)

    # The list field key should appear and map to the Inner compound child type
    assert "items" in flat
    items_field = flat["items"]
    assert isinstance(items_field, Compound)
    assert items_field.child_type is Inner

    # Scalar field should still be present
    assert "label" in flat

    # Sub-fields of Inner should also be present
    assert "items.name" in flat
    assert "items.value" in flat


def test_flat_fields_show_compound_false_excludes_list_compound_key():
    """flat_fields(show_compound=False) should NOT add the top-level key for List[Compound] fields."""

    @model()
    class Inner(Model):
        name = Keyword()

    @model()
    class Outer(Model):
        items = List(Compound(Inner))

    flat_without = Outer.flat_fields(show_compound=False)
    flat_with = Outer.flat_fields(show_compound=True)

    # With show_compound=False the 'items' key should not appear (only sub-fields)
    assert "items" not in flat_without
    assert "items.name" in flat_without

    # With show_compound=True it should appear
    assert "items" in flat_with


def test_flat_fields_show_compound_list_compound_type_is_child():
    """The value stored under the list key must be the Compound child type (not the List wrapper)."""

    @model()
    class Tag(Model):
        key = Keyword()
        count = Integer()

    @model()
    class Doc(Model):
        tags = List(Compound(Tag))

    flat = Doc.flat_fields(show_compound=True)

    assert "tags" in flat
    # Should be the Compound child type (Tag), not a List or Compound wrapper
    tags_field = flat["tags"]
    assert isinstance(tags_field, Compound)
    assert tags_field.child_type is Tag


def test_flat_fields_show_compound_nested_list_compound():
    """Multiple List[Compound] fields are all included correctly."""

    @model()
    class Alpha(Model):
        x = Keyword()

    @model()
    class Beta(Model):
        y = Integer()

    @model()
    class Container(Model):
        alphas = List(Compound(Alpha))
        betas = List(Compound(Beta))

    flat = Container.flat_fields(show_compound=True)

    assert "alphas" in flat
    alphas_field = flat["alphas"]
    assert isinstance(alphas_field, Compound)
    assert alphas_field.child_type is Alpha
    assert "betas" in flat
    betas_field = flat["betas"]
    assert isinstance(betas_field, Compound)
    assert betas_field.child_type is Beta


def test_model_id_field_default():
    """When id_field is not specified, it should default to '<classname_lower>_id'."""

    @model()
    class MyDocument(Model):
        title = Keyword()

    assert MyDocument._Model__id_field == "mydocument_id"


def test_model_id_field_explicit():
    """An explicit id_field value should be stored verbatim."""

    @model(id_field="custom_id")
    class MyRecord(Model):
        name = Keyword()

    assert MyRecord._Model__id_field == "custom_id"


def test_model_id_field_none_uses_default():
    """Passing id_field=None explicitly should also produce the default '<classname_lower>_id'."""

    @model(id_field=None)
    class SomeModel(Model):
        value = Integer()

    assert SomeModel._Model__id_field == "somemodel_id"


def test_model_id_field_stored_on_class():
    """The id_field should be accessible via cls._Model__id_field (not instance-level)."""

    @model(id_field="doc_id")
    class Document(Model):
        body = Keyword()

    # Accessible on the class directly
    assert Document._Model__id_field == "doc_id"

    # Also consistent across instances (class attribute, not instance attribute)
    instance = Document({"body": "hello"})
    assert type(instance)._Model__id_field == "doc_id"


def test_model_id_field_independent_per_class():
    """Each model class should store its own id_field independently."""

    @model(id_field="alpha_key")
    class Alpha(Model):
        x = Keyword()

    @model(id_field="beta_key")
    class Beta(Model):
        y = Keyword()

    @model()
    class Gamma(Model):
        z = Keyword()

    assert Alpha._Model__id_field == "alpha_key"
    assert Beta._Model__id_field == "beta_key"
    assert Gamma._Model__id_field == "gamma_id"
