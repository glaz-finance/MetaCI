from unittest.mock import Mock

import pytest

from metaci.release.models import ImplementationStep

from ...fixtures.factories import PlanFactory, ReleaseFactory
from ..utils import (
    implementation_payload,
    send_release_webhook,
    send_start_webhook,
    send_stop_webhook,
    send_submit_webhook,
)


def test_implementation_payload(mocker, transactional_db):
    mocker.patch(
        "metaci.release.utils.settings",
        METACI_RELEASE_WEBHOOK_URL="https://webhook",
        METACI_CHANGE_CASE_URL_TEMPLATE="{case_id}",
        METACI_RELEASE_WEBHOOK_ISSUER="MetaCI",
        METACI_RELEASE_WEBHOOK_AUTH_KEY="test",
        GUS_BUS_OWNER_ID="00G",
    )
    release = ReleaseFactory()
    release.implementation_steps.set(
        [
            ImplementationStep(
                release=release,
                plan=PlanFactory(role="foo"),
                external_id="1000",
                start_time="2021-06-08T08:00:00-00:00",
                stop_time="2021-06-08T18:00:00-00:00",
            ),
        ],
        bulk=False,
    )
    result = implementation_payload("foo", "123", release)
    assert result == {
        "description": "foo",
        "owner": "00G",
        "start_time": "2021-06-08T08:00:00-07:00",
        "end_time": "2021-06-08T18:00:00-07:00",
        "configuration_item": "123",
        "implementation_steps": "foo",
    }


def test_implementation_payload_error(mocker, transactional_db):
    mocker.patch(
        "metaci.release.utils.settings",
        METACI_RELEASE_WEBHOOK_URL="https://webhook",
        METACI_CHANGE_CASE_URL_TEMPLATE="{case_id}",
        METACI_RELEASE_WEBHOOK_ISSUER="MetaCI",
        METACI_RELEASE_WEBHOOK_AUTH_KEY="test",
        GUS_BUS_OWNER_ID="00G",
    )
    release = ReleaseFactory()
    release.implementation_steps.set(
        [
            ImplementationStep(
                release=release,
                plan=PlanFactory(role="foo"),
                external_id="1000",
                start_time="2021-06-08T08:00:00+00:00",
                stop_time="2021-06-09T18:00:00+00:00",
            ),
        ],
        bulk=False,
    )
    with pytest.raises(Exception):
        implementation_payload(None, "123", release)


def test_send_release_webhook(mocked_responses, mocker, transactional_db):
    mocker.patch(
        "metaci.release.utils.settings",
        METACI_RELEASE_WEBHOOK_URL="https://webhook",
        METACI_CHANGE_CASE_URL_TEMPLATE="{case_id}",
        METACI_RELEASE_WEBHOOK_ISSUER="MetaCI",
        METACI_RELEASE_WEBHOOK_AUTH_KEY="test",
        GUS_BUS_OWNER_ID="00G",
    )

    mocked_responses.add(
        "POST",
        "https://webhook/release/",
        json={
            "success": True,
            "implementationSteps": ["2", "1", "3"],
            "id": "2",
        },  # testing that if one of the two lists has extra items they are ignored.
    )

    project_config = Mock(project__package__name="Test Package")
    project_config.get_version_for_tag.return_value = "1.0"
    release = ReleaseFactory()
    test_plan = PlanFactory()
    second_plan = PlanFactory(role="foo")
    release.implementation_steps.set(
        [
            ImplementationStep(
                release=release,
                plan=test_plan,
                external_id="",
                start_time="2021-06-08T08:00:00+00:00",
                stop_time="2021-06-09T18:00:00+00:00",
            ),
            ImplementationStep(
                release=release,
                plan=second_plan,
                external_id="",
                start_time="2021-06-08T08:00:00+00:00",
                stop_time="2021-06-09T18:00:00+00:00",
            ),
        ],
        bulk=False,
    )
    send_release_webhook(release, "INFRA.instance1")
    assert release.implementation_steps.get(plan__role="test").external_id == "2"
    assert release.implementation_steps.get(plan__role="foo").external_id == "1"
    assert release.change_case_link == "2"


def test_send_release_webhook__disabled(mocked_responses):
    send_release_webhook(None, None)
    assert len(mocked_responses.calls) == 0


def test_send_release_webhook__error(mocked_responses, mocker, transactional_db):
    mocker.patch(
        "metaci.release.utils.settings",
        METACI_RELEASE_WEBHOOK_URL="https://webhook",
        METACI_RELEASE_WEBHOOK_ISSUER="MetaCI",
        METACI_RELEASE_WEBHOOK_AUTH_KEY="test",
    )
    mocked_responses.add(
        "POST",
        "https://webhook/release/",
        json={
            "success": False,
            "errors": [
                {"message": "ImplementationStep matching query does not exist."}
            ],
        },
    )

    project_config = Mock(project__package__name="Test Package")
    project_config.get_version_for_tag.return_value = "1.0"
    release = ReleaseFactory()

    with pytest.raises(
        Exception, match="ImplementationStep matching query does not exist."
    ):
        send_release_webhook(release, "INFRA.instance1")


def test_send_submit_webhook(mocked_responses, mocker, transactional_db):
    mocker.patch(
        "metaci.release.utils.settings",
        METACI_RELEASE_WEBHOOK_URL="https://webhook",
        METACI_CHANGE_CASE_URL_TEMPLATE="{case_id}",
        METACI_RELEASE_WEBHOOK_ISSUER="MetaCI",
        METACI_RELEASE_WEBHOOK_AUTH_KEY="test",
    )
    mocked_responses.add(
        "POST",
        "https://webhook/case/2/submit",
        json={
            "results": [{"success": True, "id": "a2d0u000000tDYeAAM"}],
            "hasErrors": False,
        },
    )

    project_config = Mock(project__package__name="Test Package")
    project_config.get_version_for_tag.return_value = "1.0"
    release = ReleaseFactory()
    release.change_case_link = "2"
    send_submit_webhook(release, "INFRA.instance1")
    assert len(mocked_responses.calls) == 1


def test_send_submit_webhook__disabled(mocked_responses):
    send_submit_webhook(None, None)
    assert len(mocked_responses.calls) == 0


def test_send_submit_webhook__error(mocked_responses, mocker, transactional_db):
    mocker.patch(
        "metaci.release.utils.settings",
        METACI_RELEASE_WEBHOOK_URL="https://webhook",
        METACI_RELEASE_WEBHOOK_ISSUER="MetaCI",
        METACI_RELEASE_WEBHOOK_AUTH_KEY="test",
    )
    mocked_responses.add(
        "POST",
        "https://webhook/case/None/submit",
        json={
            "results": [
                {
                    "success": False,
                    "errors": [
                        {
                            "message": "Update failed. First exception on row 0 with id 5000u000001DwaTAAS; first error: FIELD_CUSTOM_VALIDATION_EXCEPTION, Only Case Owners are allowed to submit for approval",
                            "errorCode": "System.DmlException",
                        }
                    ],
                }
            ],
            "hasErrors": True,
        },
    )

    with pytest.raises(Exception):
        send_submit_webhook(ReleaseFactory(), "INFRA.instance1")


def test_send_start_webhook(mocked_responses, mocker, transactional_db):
    mocker.patch(
        "metaci.release.utils.settings",
        METACI_RELEASE_WEBHOOK_URL="https://webhook",
        METACI_CHANGE_CASE_URL_TEMPLATE="{case_id}",
        METACI_RELEASE_WEBHOOK_ISSUER="MetaCI",
        METACI_RELEASE_WEBHOOK_AUTH_KEY="test",
    )
    mocked_responses.add(
        "POST",
        "https://webhook/implementation/1000/start/",
        json={
            "results": [{"success": True, "id": "a2d0u000000tDYeAAM"}],
            "hasErrors": False,
        },
    )
    project_config = Mock(project__package__name="Test Package")
    project_config.get_version_for_tag.return_value = "1.0"
    release = ReleaseFactory()
    plan = PlanFactory(role="foo")
    release.implementation_steps.set(
        [
            ImplementationStep(
                release=release,
                plan=plan,
                external_id="1000",
                start_time="2021-06-08T08:00:00+00:00",
                stop_time="2021-06-09T18:00:00+00:00",
            ),
        ],
        bulk=False,
    )
    release.change_case_link = "2"
    send_start_webhook(release, "foo", "INFRA.instance1")
    assert len(mocked_responses.calls) == 1


def test_send_start_webhook__disabled(mocked_responses):
    send_start_webhook(None, None, None)
    assert len(mocked_responses.calls) == 0


def test_send_start_webhook_failed_result_with_config(
    mocked_responses, mocker, transactional_db
):
    mocker.patch(
        "metaci.release.utils.settings",
        METACI_RELEASE_WEBHOOK_URL="https://webhook",
        METACI_CHANGE_CASE_URL_TEMPLATE="{case_id}",
        METACI_RELEASE_WEBHOOK_ISSUER="MetaCI",
        METACI_RELEASE_WEBHOOK_AUTH_KEY="test",
    )
    mocked_responses.add(
        "POST",
        "https://webhook/implementation/1000/start/",
        json={
            "results": [
                {
                    "success": False,
                    "id": "a2d0u000000tEzHAAU",
                    "errors": [
                        {
                            "message": {
                                "blockedLock": {
                                    "configurationItem": {
                                        "id": "a7JB0000000LajBMAS",
                                        "name": "NA91",
                                        "path": "Salesforce.SFDC_Core.IA2.IA2-SP1.NA91",
                                    },
                                    "title": "Free Text",
                                },
                                "blockingLocks": [
                                    {
                                        "blockingLock": {
                                            "configurationItem": {
                                                "id": "a7JB00000004GHBMA2",
                                                "path": "Salesforce.SFDC_Core.IA2",
                                            },
                                            "id": "a8L0u0000004MFrEAM",
                                            "lockCase": {},
                                            "lockOwner": {
                                                "email": "phiggins@salesforce.com",
                                                "id": "005B0000000h4eWIAQ",
                                                "name": "Paul Higgins",
                                            },
                                            "lockType": {
                                                "id": "a8KB0000000CcbxMAC",
                                                "name": "Moratorium",
                                            },
                                        }
                                    }
                                ],
                                "message": "Conflicts Detected! Found 1 lock(s) for CI: NA91",
                            },
                            "fields": [],
                            "errorCode": "FIELD_CUSTOM_VALIDATION_EXCEPTION",
                        }
                    ],
                }
            ],
            "hasErrors": True,
        },
    )
    release = ReleaseFactory()
    release.implementation_steps.set(
        [
            ImplementationStep(
                release=release,
                plan=PlanFactory(role="foo"),
                external_id="1000",
                start_time="2021-06-08T08:00:00+00:00",
                stop_time="2021-06-09T18:00:00+00:00",
            ),
        ],
        bulk=False,
    )
    with pytest.raises(Exception):
        send_start_webhook(release, "foo", "INFRA.instance1")


def test_send_start_webhook_failed_result_no_config(mocker, transactional_db):
    mocker.patch(
        "metaci.release.utils.settings",
        METACI_RELEASE_WEBHOOK_URL="https://webhook",
        METACI_CHANGE_CASE_URL_TEMPLATE="{case_id}",
        METACI_RELEASE_WEBHOOK_ISSUER="MetaCI",
        METACI_RELEASE_WEBHOOK_AUTH_KEY="test",
    )
    release = ReleaseFactory()
    release.implementation_steps.set(
        [
            ImplementationStep(
                release=release,
                plan=PlanFactory(role="foo"),
                external_id="1000",
                start_time="2021-06-08T08:00:00+00:00",
                stop_time="2021-06-09T18:00:00+00:00",
            ),
        ],
        bulk=False,
    )
    with pytest.raises(Exception):
        send_start_webhook(release, "foo", None)


def test_send_stop_webhook(mocked_responses, mocker, transactional_db):
    mocker.patch(
        "metaci.release.utils.settings",
        METACI_RELEASE_WEBHOOK_URL="https://webhook",
        METACI_CHANGE_CASE_URL_TEMPLATE="{case_id}",
        METACI_RELEASE_WEBHOOK_ISSUER="MetaCI",
        METACI_RELEASE_WEBHOOK_AUTH_KEY="test",
    )
    mocked_responses.add(
        "POST",
        "https://webhook/implementation/1000/stop/",
        json={
            "results": [{"success": True, "id": "a2d0u000000tDYeAAM"}],
            "hasErrors": False,
        },
    )
    project_config = Mock(project__package__name="Test Package")
    project_config.get_version_for_tag.return_value = "1.0"
    release = ReleaseFactory()
    plan = PlanFactory(role="foo")
    release.implementation_steps.set(
        [
            ImplementationStep(
                release=release,
                plan=plan,
                external_id="1000",
                start_time="2021-06-08T08:00:00+00:00",
                stop_time="2021-06-09T18:00:00+00:00",
            ),
        ],
        bulk=False,
    )
    release.change_case_link = "2"
    send_stop_webhook(release, "foo", "INFRA.instance1")
    assert len(mocked_responses.calls) == 1


def test_send_stop_webhook__disabled(mocked_responses):
    send_stop_webhook(None, None, None)
    assert len(mocked_responses.calls) == 0


def test_send_stop_webhook_failed_result_with_config(
    mocked_responses, mocker, transactional_db
):
    mocker.patch(
        "metaci.release.utils.settings",
        METACI_RELEASE_WEBHOOK_URL="https://webhook",
        METACI_CHANGE_CASE_URL_TEMPLATE="{case_id}",
        METACI_RELEASE_WEBHOOK_ISSUER="MetaCI",
        METACI_RELEASE_WEBHOOK_AUTH_KEY="test",
    )
    mocked_responses.add(
        "POST",
        "https://webhook/implementation/1000/stop/",
        json={
            "results": [
                {
                    "success": False,
                    "id": "a2d0u000000tEzHAAU",
                    "errors": [
                        {
                            "message": {
                                "blockedLock": {
                                    "configurationItem": {
                                        "id": "a7JB0000000LajBMAS",
                                        "name": "NA91",
                                        "path": "Salesforce.SFDC_Core.IA2.IA2-SP1.NA91",
                                    },
                                    "title": "Free Text",
                                },
                                "blockingLocks": [
                                    {
                                        "blockingLock": {
                                            "configurationItem": {
                                                "id": "a7JB00000004GHBMA2",
                                                "path": "Salesforce.SFDC_Core.IA2",
                                            },
                                            "id": "a8L0u0000004MFrEAM",
                                            "lockCase": {},
                                            "lockOwner": {
                                                "email": "phiggins@salesforce.com",
                                                "id": "005B0000000h4eWIAQ",
                                                "name": "Paul Higgins",
                                            },
                                            "lockType": {
                                                "id": "a8KB0000000CcbxMAC",
                                                "name": "Moratorium",
                                            },
                                        }
                                    }
                                ],
                                "message": "Conflicts Detected! Found 1 lock(s) for CI: NA91",
                            },
                            "fields": [],
                            "errorCode": "FIELD_CUSTOM_VALIDATION_EXCEPTION",
                        }
                    ],
                }
            ],
            "hasErrors": True,
        },
    )
    release = ReleaseFactory()
    release.implementation_steps.set(
        [
            ImplementationStep(
                release=release,
                plan=PlanFactory(role="foo"),
                external_id="1000",
                start_time="2021-06-08T08:00:00+00:00",
                stop_time="2021-06-09T18:00:00+00:00",
            ),
        ],
        bulk=False,
    )
    with pytest.raises(Exception):
        send_stop_webhook(release, "foo", "INFRA.instance1")


def test_send_stop_webhook_failed_result_no_config(mocker, transactional_db):
    mocker.patch(
        "metaci.release.utils.settings",
        METACI_RELEASE_WEBHOOK_URL="https://webhook",
        METACI_CHANGE_CASE_URL_TEMPLATE="{case_id}",
        METACI_RELEASE_WEBHOOK_ISSUER="MetaCI",
        METACI_RELEASE_WEBHOOK_AUTH_KEY="test",
    )
    release = ReleaseFactory()
    release.implementation_steps.set(
        [
            ImplementationStep(
                release=release,
                plan=PlanFactory(role="foo"),
                external_id="1000",
                start_time="2021-06-08T08:00:00+00:00",
                stop_time="2021-06-09T18:00:00+00:00",
            ),
        ],
        bulk=False,
    )
    with pytest.raises(Exception):
        send_stop_webhook(release, "foo", None)
