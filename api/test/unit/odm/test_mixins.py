"""Unit tests for howler.odm.mixins.DatastoreMixin and _ObjectsDescriptor."""

from unittest.mock import MagicMock, patch

import pytest

from howler.odm.mixins import DatastoreMixin

# ---------------------------------------------------------------------------
# Helpers – minimal concrete classes that use the mixin
# ---------------------------------------------------------------------------


class _FakeModel(DatastoreMixin["_FakeModel"]):
    """Minimal concrete subclass used to exercise DatastoreMixin behaviour.
    The mixin only needs ``__class__.__name__`` and the name-mangled
    ``_Model__id_field`` attribute that the real ODM Model sets.
    """

    _Model__id_field = "fake_id"

    def __init__(self, fake_id: str = "id-001"):
        self.fake_id = fake_id


class _AnotherModel(DatastoreMixin["_AnotherModel"]):
    """Second concrete subclass used to verify that index names are class-specific."""

    _Model__id_field = "another_id"

    def __init__(self, another_id: str = "id-002"):
        self.another_id = another_id


class _SubModel:
    """Subclass of _FakeModel to verify that index name and ID field are inherited correctly."""

    def __init__(self, fake_id: str = "id-004"):
        self.id = fake_id


class _DottedIDModel(DatastoreMixin["_DottedIDModel"]):
    """Model with a dotted ID field to verify that save() correctly looks up the ID field name."""

    _Model__id_field = "dotted.id"

    def __init__(self, fake_id: str = "id-004"):
        self.dotted = _SubModel(fake_id)


# ---------------------------------------------------------------------------
# _ObjectsDescriptor / DatastoreMixin.store
# ---------------------------------------------------------------------------


class TestStoreDescriptor:
    """Tests for the class-level ``store`` descriptor."""

    @patch("howler.odm.mixins.datastore")
    def test_store_accessed_via_class_returns_collection(self, mock_datastore):
        """Accessing Model.store via the class returns the ESCollection for that model."""
        mock_collection = MagicMock()
        mock_datastore.return_value.__getitem__.return_value = mock_collection

        result = _FakeModel.store

        mock_datastore.return_value.__getitem__.assert_called_once_with("_fakemodel")
        assert result is mock_collection

    @patch("howler.odm.mixins.datastore")
    def test_store_index_name_is_lowercase_class_name(self, mock_datastore):
        """store derives the index name from the lowercase class name."""
        _FakeModel.store
        _AnotherModel.store

        calls = [call[0][0] for call in mock_datastore.return_value.__getitem__.call_args_list]
        assert "_fakemodel" in calls
        assert "_anothermodel" in calls

    @patch("howler.odm.mixins.datastore")
    def test_store_different_classes_use_different_indexes(self, mock_datastore):
        """Two different model classes each look up their own index."""
        _FakeModel.store
        _AnotherModel.store

        calls = [call[0][0] for call in mock_datastore.return_value.__getitem__.call_args_list]
        assert calls[0] != calls[1]

    def test_store_accessed_via_instance_raises_attribute_error(self):
        """Accessing .store on an instance raises AttributeError."""
        instance = _FakeModel()

        with pytest.raises(AttributeError) as exc_info:
            _ = instance.store

        assert "_FakeModel.store" in str(exc_info.value)
        assert "class-level" in str(exc_info.value)

    @patch("howler.odm.mixins.datastore")
    def test_store_calls_datastore_on_every_access(self, mock_datastore):
        """store calls datastore() each time it is accessed (no caching)."""
        mock_datastore.return_value.__getitem__.return_value = MagicMock()

        _FakeModel.store
        _FakeModel.store

        assert mock_datastore.call_count == 2

    def test_store_error_message_includes_class_name(self):
        """AttributeError message includes the model class name when raised from an instance."""
        instance = _FakeModel()

        with pytest.raises(AttributeError) as exc_info:
            _ = instance.store

        assert "_FakeModel" in str(exc_info.value)


# ---------------------------------------------------------------------------
# DatastoreMixin.ds
# ---------------------------------------------------------------------------


class TestDsProperty:
    """Tests for the instance-level ``ds`` property."""

    @patch("howler.odm.mixins.datastore")
    def test_ds_returns_datastore_instance(self, mock_datastore):
        """ds returns the value returned by datastore()."""
        mock_ds = MagicMock()
        mock_datastore.return_value = mock_ds

        instance = _FakeModel()
        result = instance.ds

        assert result is mock_ds

    @patch("howler.odm.mixins.datastore")
    def test_ds_calls_datastore_on_every_access(self, mock_datastore):
        """ds calls datastore() each time it is accessed (no caching)."""
        instance = _FakeModel()

        _ = instance.ds
        _ = instance.ds

        assert mock_datastore.call_count == 2

    @patch("howler.odm.mixins.datastore")
    def test_ds_is_not_accessible_via_class(self, mock_datastore):
        """Accessing ds on the class returns the property descriptor, not a datastore."""
        # Accessing a property on the class returns the property object itself
        assert isinstance(DatastoreMixin.ds, property)
        mock_datastore.assert_not_called()


# ---------------------------------------------------------------------------
# DatastoreMixin.save
# ---------------------------------------------------------------------------


class TestSaveMethod:
    """Tests for the instance-level ``save`` method."""

    @patch("howler.odm.mixins.datastore")
    def test_save_calls_collection_save_with_correct_id_and_instance(self, mock_datastore):
        """save calls ds[index].save(id, self) with the correct arguments."""
        mock_ds = MagicMock()
        mock_datastore.return_value = mock_ds

        instance = _FakeModel(fake_id="my-id")
        instance.save()

        mock_ds.__getitem__.assert_called_once_with("_fakemodel")
        mock_ds["_fakemodel"].save.assert_called_once_with("my-id", instance)

    @patch("howler.odm.mixins.datastore")
    def test_save_uses_lowercase_class_name_as_index(self, mock_datastore):
        """save derives the index name from the lowercase class name."""
        mock_ds = MagicMock()
        mock_datastore.return_value = mock_ds

        instance = _AnotherModel(another_id="another-id")
        instance.save()

        mock_ds.__getitem__.assert_called_once_with("_anothermodel")

    @patch("howler.odm.mixins.datastore")
    def test_save_returns_true_on_success(self, mock_datastore):
        """save returns True when the underlying collection.save returns True."""
        mock_ds = MagicMock()
        mock_ds.__getitem__.return_value.save.return_value = True
        mock_datastore.return_value = mock_ds

        instance = _FakeModel()
        result = instance.save()

        assert result is True

    @patch("howler.odm.mixins.datastore")
    def test_save_returns_false_on_failure(self, mock_datastore):
        """save returns False when the underlying collection.save returns False."""
        mock_ds = MagicMock()
        mock_ds.__getitem__.return_value.save.return_value = False
        mock_datastore.return_value = mock_ds

        instance = _FakeModel()
        result = instance.save()

        assert result is False

    @patch("howler.odm.mixins.datastore")
    def test_save_uses_id_field_value_from_instance(self, mock_datastore):
        """save reads the document ID from the field named by _Model__id_field."""
        mock_ds = MagicMock()
        mock_datastore.return_value = mock_ds

        instance = _FakeModel(fake_id="specific-id-123")
        instance.save()

        saved_id = mock_ds.__getitem__.return_value.save.call_args[0][0]
        assert saved_id == "specific-id-123"

    @patch("howler.odm.mixins.datastore")
    def test_save_uses_dotted_id_field_value_from_instance(self, mock_datastore):
        """save reads the document ID from the field named by _Model__id_field."""
        mock_ds = MagicMock()
        mock_datastore.return_value = mock_ds

        instance = _DottedIDModel(fake_id="specific-id-456")
        instance.save()

        saved_id = mock_ds.__getitem__.return_value.save.call_args[0][0]
        assert saved_id == "specific-id-456"

    @patch("howler.odm.mixins.datastore")
    def test_save_passes_instance_as_second_argument(self, mock_datastore):
        """save passes the model instance itself as the second argument to collection.save."""
        mock_ds = MagicMock()
        mock_datastore.return_value = mock_ds

        instance = _FakeModel(fake_id="id-abc")
        instance.save()

        saved_obj = mock_ds.__getitem__.return_value.save.call_args[0][1]
        assert saved_obj is instance

    @patch("howler.odm.mixins.datastore")
    def test_save_calls_datastore_once_per_call(self, mock_datastore):
        """save fetches the datastore exactly once per save() invocation."""
        mock_datastore.return_value = MagicMock()

        instance = _FakeModel()
        instance.save()
        instance.save()

        assert mock_datastore.call_count == 2
