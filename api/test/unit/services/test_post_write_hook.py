"""Every hit and event write path reaches the single post-write hook exactly once per changed record."""

from unittest.mock import MagicMock, call, patch

import pytest

from howler.config import CLASSIFICATION
from howler.odm.models.case import CaseRule
from howler.odm.models.event import Event
from howler.odm.models.hit import Hit
from howler.odm.randomizer import random_model_obj

HOOK = "howler.services.post_write_service.record_written"


@pytest.fixture
def hook():
    with patch(HOOK) as mock_hook:
        yield mock_hook


def _hit(hit_id: str) -> Hit:
    hit: Hit = random_model_obj(Hit)
    hit.howler.id = hit_id
    return hit


def _event(event_id: str) -> Event:
    event: Event = random_model_obj(Event)
    event.howler.id = event_id
    return event


class TestHitService:
    @patch("howler.services.hit_service.datastore")
    def test_create_hit(self, mock_ds, hook):
        from howler.services import hit_service

        mock_ds.return_value.hit.exists.return_value = False

        hit_service.create_hit("hit-1", _hit("hit-1"))

        hook.assert_called_once_with({"type": "hit", "id": "hit-1"})

    @pytest.mark.parametrize("overwrite", [False, True])
    @patch("howler.services.hit_service.datastore")
    def test_create_hits(self, mock_ds, hook, overwrite):
        from howler.services import hit_service

        mock_ds.return_value.hit.exists.return_value = False

        hit_service.create_hits([_hit("hit-1"), _hit("hit-2")], overwrite=overwrite)

        assert hook.call_args_list == [call({"type": "hit", "id": "hit-1"}), call({"type": "hit", "id": "hit-2"})]

    @patch("howler.services.hit_service.datastore")
    def test_create_hits_rejected_batch_does_not_reach_hook(self, mock_ds, hook):
        from howler.common.exceptions import ResourceExists
        from howler.services import hit_service

        mock_ds.return_value.hit.exists.side_effect = [False, True]

        with pytest.raises(ResourceExists):
            hit_service.create_hits([_hit("hit-1"), _hit("hit-2")])

        hook.assert_not_called()

    @patch("howler.services.hit_service.datastore")
    def test_overwrite_hits(self, mock_ds, hook):
        from howler.services import hit_service

        hit_service.overwrite_hits([_hit("hit-1"), _hit("hit-2")])

        assert hook.call_args_list == [call({"type": "hit", "id": "hit-1"}), call({"type": "hit", "id": "hit-2"})]

    @patch("howler.services.hit_service.comms_service")
    @patch("howler.services.hit_service.datastore")
    def test_save_hit(self, mock_ds, mock_comms, hook):
        from howler.services import hit_service

        mock_ds.return_value.hit.get.return_value = ({}, "v2")

        hit_service.save_hit(_hit("hit-1"), version="v1")

        hook.assert_called_once_with({"type": "hit", "id": "hit-1"})

    @patch("howler.services.hit_service.comms_service")
    @patch("howler.services.hit_service.datastore")
    def test_update_hit(self, mock_ds, mock_comms, hook):
        from howler.services import hit_service

        mock_ds.return_value.hit.get.return_value = (_hit("hit-1"), "v1")
        mock_ds.return_value.hit.update.return_value = (True, "v2")

        hit_service.update_hit(
            "hit-1",
            [
                hit_service.odm_helper.update("howler.assignment", "user"),
                hit_service.odm_helper.update("howler.rationale", "x"),
            ],
            user="user",
        )

        hook.assert_called_once_with({"type": "hit", "id": "hit-1"})

    @patch("howler.services.hit_service.comms_service")
    @patch("howler.services.hit_service.datastore")
    def test_failed_update_does_not_reach_hook(self, mock_ds, mock_comms, hook):
        from howler.services import hit_service

        mock_ds.return_value.hit.get.return_value = (_hit("hit-1"), "v1")
        mock_ds.return_value.hit.update.return_value = False

        hit_service.update_hit("hit-1", [hit_service.odm_helper.update("howler.assignment", "user")], user="user")

        hook.assert_not_called()

    @pytest.mark.parametrize("transition", ["release", "promote"])
    @patch("howler.services.hit_service.action_service")
    @patch("howler.services.hit_service.comms_service")
    @patch("howler.services.hit_service.get_hit_workflow")
    @patch("howler.services.hit_service.datastore")
    def test_transition_hit(self, mock_ds, mock_workflow, mock_comms, mock_actions, hook, transition):
        from howler.services import hit_service

        hit = _hit("hit-1")
        mock_ds.return_value.hit.get.return_value = (hit, "v1")
        mock_ds.return_value.hit.update.return_value = (True, "v2")
        mock_workflow.return_value.transition.return_value = [hit_service.odm_helper.update("howler.assignment", "u")]

        hit_service.transition_hit("hit-1", transition, MagicMock(uname="user"), hit=hit.as_primitives())

        hook.assert_called_once_with({"type": "hit", "id": "hit-1"})

    @patch("howler.services.hit_service.comms_service")
    @patch("howler.services.hit_service.get_hit_workflow")
    @patch("howler.services.hit_service.datastore")
    def test_transition_without_changes_does_not_reach_hook(self, mock_ds, mock_workflow, mock_comms, hook):
        from howler.services import hit_service

        hit = _hit("hit-1")
        mock_workflow.return_value.transition.return_value = []

        hit_service.transition_hit("hit-1", "start", MagicMock(uname="user"), hit=hit.as_primitives())

        hook.assert_not_called()

    @patch("howler.services.hit_service.datastore")
    def test_delete_hits_does_not_reach_hook(self, mock_ds, hook):
        from howler.services import hit_service

        hit_service.delete_hits({"hit-1"})

        hook.assert_not_called()


class TestEventService:
    @patch("howler.services.event_service.datastore")
    def test_create_event(self, mock_ds, hook):
        from howler.services import event_service

        mock_ds.return_value.event.exists.return_value = False

        event_service.create_event("event-1", _event("event-1"))

        hook.assert_called_once_with({"type": "event", "id": "event-1"})

    @pytest.mark.parametrize("overwrite", [False, True])
    @patch("howler.services.event_service.datastore")
    def test_create_events(self, mock_ds, hook, overwrite):
        from howler.services import event_service

        mock_ds.return_value.event.exists.return_value = False

        event_service.create_events([_event("event-1"), _event("event-2")], overwrite=overwrite)

        assert hook.call_args_list == [
            call({"type": "event", "id": "event-1"}),
            call({"type": "event", "id": "event-2"}),
        ]


class TestIngestOverwrite:
    @pytest.mark.parametrize("index", ["hit", "event"])
    @patch("howler.services.ingest_service.datastore")
    def test_overwrite_record(self, mock_ds, hook, index):
        from howler.services import ingest_service

        ingest_service.overwrite_record(index, "record-1", {"howler.id": "record-1"}, version="v1")

        mock_ds.return_value[index].save.assert_called_once_with(
            "record-1", {"howler.id": "record-1"}, version="v1", refresh=None
        )
        hook.assert_called_once_with({"type": index, "id": "record-1"})

    @patch("howler.services.ingest_service.datastore")
    def test_overwrite_other_index_does_not_reach_hook(self, mock_ds, hook):
        from howler.services import ingest_service

        ingest_service.overwrite_record("case", "case-1", {"case_id": "case-1"}, version="v1")

        hook.assert_not_called()

    @patch("howler.services.ingest_service.datastore")
    def test_failed_overwrite_does_not_reach_hook(self, mock_ds, hook):
        from howler.datastore.exceptions import VersionConflictException
        from howler.services import ingest_service

        mock_ds.return_value["hit"].save.side_effect = VersionConflictException("conflict")

        with pytest.raises(VersionConflictException):
            ingest_service.overwrite_record("hit", "hit-1", {"howler.id": "hit-1"}, version="v1")

        hook.assert_not_called()


class TestMixinSave:
    @patch("howler.odm.mixins.datastore")
    def test_hit_save(self, mock_ds, hook):
        _hit("hit-1").save(version="v1")

        hook.assert_called_once_with({"type": "hit", "id": "hit-1"})

    @patch("howler.odm.mixins.datastore")
    def test_event_save(self, mock_ds, hook):
        _event("event-1").save(version="v1")

        hook.assert_called_once_with({"type": "event", "id": "event-1"})

    @patch("howler.odm.mixins.datastore")
    def test_case_save_does_not_reach_hook(self, mock_ds, hook):
        from howler.odm.models.case import Case

        case = Case({"case_id": "case-1", "title": "Case", "summary": "Summary"})
        case.save()

        hook.assert_not_called()


class TestCorrelation:
    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    @pytest.mark.parametrize("hit_bulk_succeeds", [True, False])
    def test_process_batch_backreferences(
        self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms, hook, hit_bulk_succeeds
    ):
        from howler.common.exceptions import HowlerRuntimeError
        from howler.services import correlation_service

        case = MagicMock(case_id="case-1", items=[])
        backing = {}
        for kind in ("hit", "event"):
            backing[kind] = MagicMock(classification=CLASSIFICATION.UNRESTRICTED, related=None)
            backing[kind].howler.related = []
            backing[kind].howler.outline = None

        mock_ds = mock_ds_fn.return_value
        mock_ds.__getitem__.side_effect = lambda item_type: getattr(mock_ds, item_type)
        mock_ds.case.get.return_value = (case, "1---1")
        mock_ds.hit.get.return_value = (backing["hit"], "1---1")
        mock_ds.event.get.return_value = (backing["event"], "1---1")
        for kind in ("hit", "event"):
            getattr(mock_ds, kind).get_version_write_target.return_value = (f"howler-{kind}", 1, 1)
        mock_ds.hit.bulk.return_value = hit_bulk_succeeds
        mock_ds.event.bulk.return_value = True

        rule = CaseRule(
            {
                "query": "*:*",
                "destination": "alerts",
                "author": "test_user",
                "enabled": True,
                "indexes": ["hit", "event"],
            }
        )
        mock_get_rules.return_value = [("case-1", rule)]
        mock_search_svc.search.return_value = {
            "items": [
                {"howler": {"id": "hit-1"}, "__index": "hit"},
                {"howler": {"id": "event-1"}, "__index": "event"},
            ]
        }

        if hit_bulk_succeeds:
            correlation_service.process_batch(["hit-1", "event-1"])
        else:
            with pytest.raises(HowlerRuntimeError):
                correlation_service.process_batch(["hit-1", "event-1"])

        hook.assert_any_call({"type": "hit", "id": "hit-1"})
        event_written = mock_ds.event.bulk.called
        assert ({"type": "event", "id": "event-1"} in [c.args[0] for c in hook.call_args_list]) == event_written
        assert hook.call_count == (2 if event_written else 1)
        if hit_bulk_succeeds:
            assert event_written
