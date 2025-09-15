"""Unit tests for session utility functions in Survey Assist UI.

This module contains tests for session encoding, datetime conversion, and session debug
decorators.
"""

from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from flask import current_app, session

from models.result import (
    FollowUp,
    FollowUpQuestion,
    GenericCandidate,
    GenericClassificationResult,
    GenericResponse,
    GenericSurveyAssistInteraction,
    GenericSurveyAssistResult,
    InputField,
    LookupResponse,
)
from utils.app_types import SurveyAssistFlask
from utils.session_utils import (
    _convert_datetimes,
    add_classify_interaction,
    add_follow_up_response_to_classify,
    add_follow_up_to_latest_classify,
    add_interaction_to_response,
    add_question_to_survey,
    add_sic_lookup_interaction,
    get_encoded_session_size,
    load_model_from_session,
    print_session_info,
    remove_model_from_session,
    save_model_to_session,
    session_debug,
)

# pylint cannot differentiate the use of fixtures in the test functions
# pylint: disable=unused-argument, disable=redefined-outer-name, disable=line-too-long
# pylint: disable=too-many-lines


@pytest.mark.utils
def test_session_debug_decorator_calls_view_and_prints(
    client, monkeypatch  # pylint:disable=unused-argument
):
    """Tests that session_debug calls the view function and prints session info."""
    app = cast(SurveyAssistFlask, current_app)
    mock_response = MagicMock(name="Response")

    # Fake function to decorate
    def test_view():
        return mock_response

    # Patch the session printer
    with patch("utils.session_utils.print_session_info") as mock_print:
        decorated = session_debug(test_view)

        with app.app_context():
            app.config["SESSION_DEBUG"] = True
            result = decorated()

        # Assertions
        assert result == mock_response
        mock_print.assert_called_once()


@pytest.mark.utils
def test_convert_datetimes_dict():
    """Tests that datetime values in a dictionary are converted to ISO format."""
    dt = datetime(2024, 1, 1, 12, 0, 0)
    input_data = {"key": dt}
    result = _convert_datetimes(input_data)
    assert result == {"key": dt.isoformat()}


@pytest.mark.utils
def test_convert_datetimes_list():
    """Tests that datetime values in a list are converted to ISO format."""
    dt = datetime(2023, 6, 15, 8, 30)
    input_data = [dt]
    result = _convert_datetimes(input_data)
    assert result == [dt.isoformat()]


@pytest.mark.utils
def test_convert_datetimes_nested_structures():
    """Tests that datetime values in nested dicts and lists are converted."""
    dt = datetime(2022, 12, 25, 0, 0)
    input_data = {
        "outer": {
            "inner": [dt, {"deep": dt}],
        }
    }
    result = _convert_datetimes(input_data)
    assert result == {
        "outer": {
            "inner": [dt.isoformat(), {"deep": dt.isoformat()}],
        }
    }


@pytest.mark.utils
def test_convert_datetimes_primitive_passthrough():
    """Tests that non-datetime primitive values are returned unchanged."""
    assert _convert_datetimes("string") == "string"
    assert _convert_datetimes(42) == 42  # noqa: PLR2004
    assert _convert_datetimes(None) is None
    assert _convert_datetimes(3.14) == 3.14  # noqa: PLR2004
    assert _convert_datetimes(True) is True


@pytest.mark.utils
def test_get_encoded_session_size_returns_byte_length(
    client,
):  # pylint:disable=unused-argument
    """Tests that get_encoded_session_size returns correct byte size of session object."""
    app = cast(SurveyAssistFlask, current_app)

    session_data = {"user": "test", "logged_in": True}
    with app.app_context():
        size = get_encoded_session_size(session_data)
        assert isinstance(size, int)
        assert size > 0


@pytest.mark.utils
def test_get_encoded_session_size_returns_zero_if_no_serializer(
    client,
):  # pylint:disable=unused-argument
    """Tests that get_encoded_session_size returns 0 if serializer is None."""
    app = cast(SurveyAssistFlask, current_app)
    with (
        patch(
            "utils.session_utils.SecureCookieSessionInterface.get_signing_serializer",
            return_value=None,
        ),
        app.app_context(),
    ):
        result = get_encoded_session_size({"any": "data"})
        assert result == 0


@pytest.mark.utils
def test_print_session_info_debug_disabled(app):
    """Should return early if SESSION_DEBUG is False."""
    with app.test_request_context():
        app.config["SESSION_DEBUG"] = False
        with patch("utils.session_utils.logger.debug") as mock_debug:
            print_session_info()
            mock_debug.assert_not_called()


@pytest.mark.utils
def test_print_session_info_json_debug_false(app):
    """Should log size but not session content if JSON_DEBUG is False."""
    with app.test_request_context():
        app.config["SESSION_DEBUG"] = True
        app.config["JSON_DEBUG"] = False
        session["foo"] = "bar"
        with patch("utils.session_utils.logger.debug") as mock_debug, patch(
            "utils.session_utils.get_encoded_session_size", return_value=123
        ):
            print_session_info()
            debug_calls = [call.args[0] for call in mock_debug.call_args_list]
            assert any("Session size: 123 bytes" in msg for msg in debug_calls)
            assert not any("Session content:" in msg for msg in debug_calls)


@pytest.mark.utils
def test_print_session_info_full_output(app):
    """Should log both size and session content when all debug flags enabled."""
    with app.test_request_context():
        app.config["SESSION_DEBUG"] = True
        app.config["JSON_DEBUG"] = True
        session["key"] = "value"
        with patch("utils.session_utils.logger.debug") as mock_debug, patch(
            "utils.session_utils.get_encoded_session_size", return_value=456
        ):
            print_session_info()
            debug_calls = [call.args[0] for call in mock_debug.call_args_list]
            assert any("Session size: 456 bytes" in msg for msg in debug_calls)
            assert any("Session content:" in msg for msg in debug_calls)


@pytest.mark.utils
def test_print_session_info_raises_and_logs_error(app):
    """Should catch and log exceptions that occur during session processing."""
    with app.test_request_context():
        app.config["SESSION_DEBUG"] = True
        session["bad"] = object()  # Unserialisable

        with patch(
            "utils.session_utils.get_encoded_session_size", side_effect=TypeError("bad")
        ), patch("utils.session_utils.logger.error") as mock_error:
            print_session_info()
            mock_error.assert_called_once()
            assert "Error printing session debug info" in mock_error.call_args[0][0]


@pytest.mark.utils
def test_add_question_success(app, valid_question: dict[str, Any]) -> None:
    """Test successful addition of question and response to session."""
    with app.test_request_context():
        session["survey_iteration"] = {"questions": []}
        add_question_to_survey(valid_question, "Pilot")

        assert len(session["survey_iteration"]["questions"]) == 1
        added = session["survey_iteration"]["questions"][0]
        assert added["question_id"] == "q1"
        assert added["response"] == "Pilot"
        assert added["used_for_classifications"] == ["sic", "soc"]
        assert session.modified is True


@pytest.mark.utils
def test_add_question_user_response_none_success(
    app, valid_question: dict[str, Any]
) -> None:
    """Test successful addition of question and response to session."""
    with app.test_request_context():
        session["survey_iteration"] = {"questions": []}
        add_question_to_survey(valid_question, None)

        assert len(session["survey_iteration"]["questions"]) == 1
        added = session["survey_iteration"]["questions"][0]
        assert added["question_id"] == "q1"
        assert added["response"] is None
        assert added["used_for_classifications"] == ["sic", "soc"]
        assert session.modified is True


@pytest.mark.utils
def test_missing_required_keys(app, valid_question: dict[str, Any]) -> None:
    """Test ValueError raised when required keys are missing from question."""
    del valid_question["response_name"]
    with app.test_request_context():
        session["survey_iteration"] = {"questions": []}
        with pytest.raises(ValueError) as exc:
            add_question_to_survey(valid_question, "Pilot")

        assert "missing keys" in str(exc.value)


@pytest.mark.utils
def test_missing_survey_iteration_raises_keyerror(
    app, valid_question: dict[str, Any]
) -> None:
    """Test KeyError raised when session lacks survey_iteration."""
    with app.test_request_context():
        with pytest.raises(KeyError) as exc:
            add_question_to_survey(valid_question, "Pilot")

        assert "survey_iteration" in str(exc.value)


@pytest.mark.utils
def test_missing_questions_in_survey_iteration(
    app, valid_question: dict[str, Any]
) -> None:
    """Test KeyError raised when 'questions' key is missing in survey_iteration."""
    with app.test_request_context():
        session["survey_iteration"] = {}
        with pytest.raises(KeyError) as exc:
            add_question_to_survey(valid_question, "Pilot")

        assert "Session does not contain a valid 'survey_iteration' structure." in str(
            exc.value
        )


@pytest.mark.utils
def test_optional_fields_default(app, valid_question: dict[str, Any]) -> None:
    """Test that optional fields default if missing."""
    del valid_question["used_for_classifications"]

    with app.test_request_context():
        session["survey_iteration"] = {"questions": []}
        add_question_to_survey(valid_question, "Checkout Assistant")

        added = session["survey_iteration"]["questions"][0]
        assert added["used_for_classifications"] == []


# Add fixture in-line. This is because there is conflict in the pydantic models between
# Classify and Results. They both have models with the same names, but different structures.
# The models need to be rationalised and this fixture can be moved into conftest.
@pytest.fixture
def nested_survey_result_model() -> GenericSurveyAssistResult:
    """survey_result model test fixture."""
    return GenericSurveyAssistResult(
        survey_id="shape_tomorrow_prototype",
        case_id="test-case-xyz",
        user="user.respondent-a",
        time_start=datetime.fromisoformat("2025-08-11T15:29:14.427109+00:00"),
        time_end=datetime.fromisoformat("2025-08-11T15:29:47.719649+00:00"),
        responses=[
            GenericResponse(
                person_id="user.respondent-a",
                time_start=datetime.fromisoformat("2025-08-11T15:29:14.427109+00:00"),
                time_end=datetime.fromisoformat("2025-08-11T15:29:47.719649+00:00"),
                survey_assist_interactions=[
                    GenericSurveyAssistInteraction(
                        type="lookup",
                        flavour="sic",
                        time_start=datetime.fromisoformat(
                            "2025-08-11T15:29:32.414630+00:00"
                        ),
                        time_end=datetime.fromisoformat(
                            "2025-08-11T15:29:32.562933+00:00"
                        ),
                        input=[
                            InputField(
                                field="org_description",
                                value="Farm providing food for shops and wholesalers",
                            )
                        ],
                        response=LookupResponse(
                            found=False,
                            code="",
                            code_division=None,
                            potential_codes_count=0,
                            potential_divisions=[],
                            potential_codes=[],
                        ),
                    ),
                    GenericSurveyAssistInteraction(
                        type="classify",
                        flavour="sic",
                        time_start=datetime.fromisoformat(
                            "2025-08-11T15:29:47.719649+00:00"
                        ),
                        time_end=datetime.fromisoformat(
                            "2025-08-11T15:29:47.719649+00:00"
                        ),
                        input=[
                            InputField(field="job_title", value="Farm Hand"),
                            InputField(
                                field="job_description",
                                value="I tend crops on a farm applying fertaliser and harvesting plants",
                            ),
                            InputField(
                                field="org_description",
                                value="Farm providing food for shops and wholesalers",
                            ),
                        ],
                        response=[
                            GenericClassificationResult(
                                type="sic",
                                classified=False,
                                code="46210",
                                description="Wholesale of grain, unmanufactured tobacco, seeds and animal feeds",
                                reasoning="The company's main activity is farming and providing food...",
                                candidates=[
                                    GenericCandidate(
                                        code="46210",
                                        descriptive="Wholesale of grain, unmanufactured tobacco, seeds and animal feeds",
                                        likelihood=0.6,
                                    ),
                                    GenericCandidate(
                                        code="46390",
                                        descriptive="Non-specialised wholesale of food, beverages and tobacco",
                                        likelihood=0.4,
                                    ),
                                ],
                                follow_up=FollowUp(
                                    questions=[
                                        FollowUpQuestion(
                                            id="f1.1",
                                            text="Does your farm primarily sell grain, seeds, animal feeds, or other types of food products?",
                                            type="text",
                                            select_options=[],
                                            response="sells animal feeds",
                                        ),
                                        FollowUpQuestion(
                                            id="f1.2",
                                            text="Which of these best describes your organisation's activities?",
                                            type="select",
                                            select_options=[
                                                "Wholesale of grain, unmanufactured tobacco, seeds and animal feeds",
                                                "Non-specialised wholesale of food, beverages and tobacco",
                                                "None of the above",
                                            ],
                                            response="none of the above",
                                        ),
                                    ]
                                ),
                            )
                        ],
                    ),
                ],
            )
        ],
    )


@pytest.mark.utils
def test_save_model_to_session(
    app, nested_survey_result_model: GenericSurveyAssistResult
) -> None:
    """Successfully save survey_result in session."""
    with app.test_request_context():
        save_model_to_session("survey_result", nested_survey_result_model)
        assert "survey_result" in session
        assert isinstance(session["survey_result"], dict)
        assert session["survey_result"]["user"] == "user.respondent-a"


@pytest.mark.utils
def test_load_model_from_session(
    app, nested_survey_result_model: GenericSurveyAssistResult
) -> None:
    """Successfully load survey_result model."""
    with app.test_request_context():
        save_model_to_session("survey_result", nested_survey_result_model)
        loaded = load_model_from_session("survey_result", GenericSurveyAssistResult)
        assert isinstance(loaded, GenericSurveyAssistResult)
        assert loaded.user == nested_survey_result_model.user
        assert loaded.responses[0].survey_assist_interactions[0].flavour == "sic"


@pytest.mark.utils
def test_remove_model_from_session(
    app, nested_survey_result_model: GenericSurveyAssistResult
) -> None:
    """Successfully remove survey_result model."""
    with app.test_request_context():
        save_model_to_session("survey_result", nested_survey_result_model)
        assert "survey_result" in session
        remove_model_from_session("survey_result")
        assert "survey_result" not in session
        assert session.modified is True


@pytest.mark.utils
def test_load_model_with_corrupted_data(app) -> None:
    """Check error is raised when session includes invalid model structure."""
    with app.test_request_context():
        # Insert invalid structure (missing required fields)
        session["survey_result"] = {"invalid": "structure"}
        with pytest.raises(Exception) as exc_info:
            _ = load_model_from_session("survey_result", GenericSurveyAssistResult)
        assert (
            "model_validate" in str(exc_info.value)
            or "validation" in str(exc_info.value).lower()
        )


@pytest.mark.utils
def test_load_model_with_missing_key(app) -> None:
    """Check error is raised when survey_result key does not exist."""
    with app.test_request_context():  # noqa: SIM117
        # Key not set at all
        with pytest.raises(KeyError):
            _ = load_model_from_session("survey_result", GenericSurveyAssistResult)


# Add fixture in-line. This is because there is conflict in the pydantic models between
# Classify and Results. They both have models with the same names, but different structures.
# The models need to be rationalised and this fixture can be moved into conftest.
@pytest.fixture
def base_result() -> GenericSurveyAssistResult:
    """Survey assist result test fixture."""
    return GenericSurveyAssistResult(
        survey_id="survey-xyz",
        case_id="case-abc",
        user="test.user",
        time_start=datetime(2025, 8, 13, 10, 0),
        time_end=datetime(2025, 8, 13, 10, 5),
        responses=[
            GenericResponse(
                person_id="user.respondent-a",
                time_start=datetime(2025, 8, 13, 10, 0),
                time_end=datetime(2025, 8, 13, 10, 2),
                survey_assist_interactions=[],
            )
        ],
    )


@pytest.fixture
def example_interaction() -> GenericSurveyAssistInteraction:
    """Survey assist interaction test fixture."""
    return GenericSurveyAssistInteraction(
        type="lookup",
        flavour="sic",
        time_start=datetime(2025, 8, 13, 10, 4),
        time_end=datetime(2025, 8, 13, 10, 6),
        input=[],
        response=LookupResponse(
            found=True,
            code="54321",
            code_division="54",
            potential_codes_count=0,
            potential_codes=[],
            potential_divisions=[],
        ),
    )


@pytest.mark.utils
def test_add_interaction_success(
    base_result: GenericSurveyAssistResult,
    example_interaction: GenericSurveyAssistInteraction,
) -> None:
    """Successfully add interaction to survey_result."""
    updated = add_interaction_to_response(
        base_result, "user.respondent-a", example_interaction
    )

    assert len(updated.responses[0].survey_assist_interactions) == 1
    assert updated.responses[0].survey_assist_interactions[0] == example_interaction
    assert updated.responses[0].time_end == example_interaction.time_end
    assert updated.time_end == example_interaction.time_end


INPUT_LEN = 2


@pytest.mark.utils
def test_add_interaction_with_input_fields(
    base_result: GenericSurveyAssistResult,
    example_interaction: GenericSurveyAssistInteraction,
) -> None:
    """Successfully add interaction with input_fields to survey_result."""
    input_fields = {"job_title": "Developer", "org_description": "Tech Company"}

    updated = add_interaction_to_response(
        base_result, "user.respondent-a", example_interaction, input_fields
    )

    inputs = updated.responses[0].survey_assist_interactions[0].input
    assert len(inputs) == INPUT_LEN
    assert any(i.field == "job_title" and i.value == "Developer" for i in inputs)
    assert any(
        i.field == "org_description" and i.value == "Tech Company" for i in inputs
    )


@pytest.mark.utils
def test_add_interaction_no_matching_person(
    base_result: GenericSurveyAssistResult,
    example_interaction: GenericSurveyAssistInteraction,
) -> None:
    """Raise error when person is not found in survey_result."""
    with pytest.raises(
        ValueError, match="No response found for person_id 'non-existent'"
    ):
        add_interaction_to_response(base_result, "non-existent", example_interaction)


@pytest.mark.utils
def test_add_interaction_result_time_not_updated_if_earlier(
    base_result: GenericSurveyAssistResult,
    example_interaction: GenericSurveyAssistInteraction,
) -> None:
    """Test invalid time (end time before existing end time) behaviour."""
    # Change interaction time_end to earlier than result_model.time_end
    example_interaction.time_end = datetime(2025, 8, 13, 10, 1)

    updated = add_interaction_to_response(
        base_result, "user.respondent-a", example_interaction
    )

    assert updated.responses[0].time_end == example_interaction.time_end
    assert updated.time_end == datetime(2025, 8, 13, 10, 5)


CODES_LEN = 2


@pytest.mark.utils
def test_add_sic_lookup_interaction_adds_interaction(
    app, base_result: GenericSurveyAssistResult
) -> None:
    """Successfully add a sic lookup interaction."""
    with app.test_request_context():
        # Save initial model to session
        save_model_to_session("survey_result", base_result)

        # Create fake SIC API response
        fake_sic_response = {
            "code": "46210",
            "potential_matches": {
                "codes": ["46210", "46390"],
                "codes_count": 2,
                "divisions": [
                    {
                        "code": "46",
                        "meta": {
                            "title": "Wholesale trade",
                            "detail": "Selling products to retailers",
                        },
                    }
                ],
                "divisions_count": 1,
            },
        }

        input_fields = {
            "org_description": "Farming and distribution",
            "job_title": "Farm Hand",
        }

        start_time = datetime(2025, 8, 13, 10, 6)
        end_time = datetime(2025, 8, 13, 10, 7)

        add_sic_lookup_interaction(
            lookup_resp=fake_sic_response,
            start_time=start_time,
            end_time=end_time,
            inputs_dict=input_fields,
        )

        updated = load_model_from_session("survey_result", GenericSurveyAssistResult)
        interaction = updated.responses[0].survey_assist_interactions[-1]

        assert interaction.type == "lookup"
        assert interaction.flavour == "sic"
        assert interaction.time_start == start_time
        assert interaction.time_end == end_time
        assert isinstance(interaction.response, LookupResponse)
        assert len(interaction.response.potential_codes) == CODES_LEN
        assert len(interaction.input) == INPUT_LEN
        assert any(i.field == "job_title" for i in interaction.input)
        assert updated.time_end == end_time


@pytest.mark.utils
def test_add_sic_lookup_with_missing_person(
    app, base_result: GenericSurveyAssistResult
) -> None:
    """Test no matching person-id for lookup interaction."""
    # Modify to have different person_id
    base_result.responses[0].person_id = "someone-else"
    with app.test_request_context():
        save_model_to_session("survey_result", base_result)

        with pytest.raises(ValueError, match="No response found for person_id"):
            add_sic_lookup_interaction(
                lookup_resp={"code": "123", "potential_matches": {}},
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                inputs_dict={"job_title": "Analyst"},
            )


@pytest.fixture
def classify_response() -> Any:
    """Classify response test fixture."""

    # pylint: disable=too-few-public-methods
    class MockClassifyResponse:
        """Mocked classify response."""

        def __init__(self) -> None:
            self.results = [
                GenericClassificationResult(
                    type="sic",
                    classified=True,
                    code="46210",
                    description="Wholesale of grain, unmanufactured tobacco, seeds and animal feeds",
                    reasoning="Clear match based on job description and organisation",
                    candidates=[
                        GenericCandidate(
                            code="46210", descriptive="Wholesale...", likelihood=0.8
                        ),
                        GenericCandidate(
                            code="46390",
                            descriptive="Other wholesale...",
                            likelihood=0.2,
                        ),
                    ],
                    follow_up=None,
                )
            ]

    return MockClassifyResponse()


THREE_INPUTS = 3


@pytest.mark.utils
def test_add_classify_interaction_adds_correctly(
    app,
    base_result: GenericSurveyAssistResult,
    classify_response: Any,
) -> None:
    """Successfully add a classification interaction."""
    with app.test_request_context():
        save_model_to_session("survey_result", base_result)

        input_fields = {
            "job_title": "Farm Hand",
            "job_description": "Tends crops on a farm",
            "org_description": "Agricultural provider",
        }

        start_time = datetime(2025, 8, 13, 10, 6)
        end_time = datetime(2025, 8, 13, 10, 7)

        add_classify_interaction(
            flavour="sic",
            classify_resp=classify_response,
            start_time=start_time,
            end_time=end_time,
            inputs_dict=input_fields,
        )

        result = load_model_from_session("survey_result", GenericSurveyAssistResult)
        interactions = result.responses[0].survey_assist_interactions

        assert len(interactions) == 1
        interaction = interactions[0]

        assert interaction.type == "classify"
        assert interaction.flavour == "sic"
        assert interaction.time_start == start_time
        assert interaction.time_end == end_time
        assert result.time_end == end_time
        assert len(interaction.input) == THREE_INPUTS
        assert any(f.field == "job_title" for f in interaction.input)
        assert isinstance(interaction.response, list)
        assert isinstance(interaction.response[0], GenericClassificationResult)
        assert interaction.response[0].code == "46210"


@pytest.mark.utils
def test_add_classify_interaction_invalid_person(
    app, base_result: GenericSurveyAssistResult, classify_response: Any
) -> None:
    """No match for person-id in classification interaction."""
    base_result.responses[0].person_id = "someone-else"

    with app.test_request_context():
        save_model_to_session("survey_result", base_result)

        with pytest.raises(ValueError, match="No response found for person_id"):
            add_classify_interaction(
                flavour="sic",
                classify_resp=classify_response,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                inputs_dict={"job_title": "X"},
            )


@pytest.fixture
def base_result_with_classify_model() -> GenericSurveyAssistResult:
    """Survey assist result test fixture."""
    return GenericSurveyAssistResult(
        survey_id="shape_tomorrow_prototype",
        case_id="test-case-xyz",
        user="user.respondent-a",
        time_start=datetime(2025, 8, 13, 10, 0),
        time_end=datetime(2025, 8, 13, 10, 5),
        responses=[
            GenericResponse(
                person_id="user.respondent-a",
                time_start=datetime(2025, 8, 13, 10, 0),
                time_end=datetime(2025, 8, 13, 10, 2),
                survey_assist_interactions=[
                    GenericSurveyAssistInteraction(
                        type="classify",
                        flavour="sic",
                        time_start=datetime(2025, 8, 13, 10, 1),
                        time_end=datetime(2025, 8, 13, 10, 2),
                        input=[],
                        response=[
                            GenericClassificationResult(
                                type="sic",
                                classified=True,
                                code="46210",
                                description="Description",
                                candidates=[
                                    GenericCandidate(
                                        code="46210",
                                        descriptive="Something",
                                        likelihood=0.8,
                                    )
                                ],
                                reasoning="Example reasoning",
                                follow_up=None,
                            )
                        ],
                    )
                ],
            )
        ],
    )


@pytest.fixture
def follow_up_questions() -> list[FollowUpQuestion]:
    """Follow up question test fixture."""
    return [
        FollowUpQuestion(
            id="q1",
            text="What does your organisation do?",
            type="text",
            select_options=None,
            response="We sell grain",
        )
    ]


@pytest.mark.utils
def test_add_follow_up_classify_model_response(
    app,
    base_result_with_classify_model: GenericSurveyAssistResult,
    follow_up_questions: list[FollowUpQuestion],
) -> None:
    """Successfully add folow up questions to classify interaction."""
    with app.test_request_context():
        save_model_to_session("survey_result", base_result_with_classify_model)
        updated = add_follow_up_to_latest_classify("sic", follow_up_questions)

        primary = updated.responses[0].survey_assist_interactions[0].response[0]
        assert isinstance(primary, GenericClassificationResult)
        assert primary.follow_up is not None
        assert len(primary.follow_up.questions) == 1
        assert primary.follow_up.questions[0].id == "q1"


@pytest.mark.utils
def test_add_follow_up_no_person_found(
    app,
    base_result_with_classify_model: GenericSurveyAssistResult,
    follow_up_questions: list[FollowUpQuestion],
) -> None:
    """No matching person on addition of follow up."""
    with app.test_request_context():
        save_model_to_session("survey_result", base_result_with_classify_model)

        with pytest.raises(
            ValueError, match="No responses for person_id=different-person"
        ):
            add_follow_up_to_latest_classify(
                "sic", follow_up_questions, person_id="different-person"
            )


@pytest.mark.utils
def test_add_follow_up_no_classify_found(
    app,
    base_result_with_classify_model: GenericSurveyAssistResult,
    follow_up_questions: list[FollowUpQuestion],
) -> None:
    """No matching flavour on addition of follow up."""
    # Modify flavour so it does not match
    base_result_with_classify_model.responses[0].survey_assist_interactions[
        0
    ].flavour = "soc"

    with app.test_request_context():
        save_model_to_session("survey_result", base_result_with_classify_model)

        with pytest.raises(
            ValueError, match="No classify interaction found for flavour=sic"
        ):
            add_follow_up_to_latest_classify("sic", follow_up_questions)


@pytest.mark.utils
def test_add_follow_up_wrong_type_response(
    app,
    base_result_with_classify_model: GenericSurveyAssistResult,
    follow_up_questions: list[FollowUpQuestion],
) -> None:
    """Test validation of follow up."""
    # Set interaction.response to a LookupResponse instead of list
    base_result_with_classify_model.responses[0].survey_assist_interactions[
        0
    ].response = LookupResponse(
        found=True,
        code="54321",
        code_division="54",
        potential_codes_count=0,
        potential_codes=[],
        potential_divisions=[],
    )

    with app.test_request_context():
        save_model_to_session("survey_result", base_result_with_classify_model)

        with pytest.raises(TypeError, match="Expected classification response list"):
            add_follow_up_to_latest_classify("sic", follow_up_questions)


@pytest.fixture
def survey_result_with_followup_model() -> GenericSurveyAssistResult:
    """Survey result including follow up question test fixture."""
    return GenericSurveyAssistResult(
        survey_id="test-survey",
        case_id="test-case",
        user="user.respondent-a",
        time_start=datetime(2025, 8, 13, 10, 0),
        time_end=datetime(2025, 8, 13, 10, 2),
        responses=[
            GenericResponse(
                person_id="user.respondent-a",
                time_start=datetime(2025, 8, 13, 10, 0),
                time_end=datetime(2025, 8, 13, 10, 1),
                survey_assist_interactions=[
                    GenericSurveyAssistInteraction(
                        type="classify",
                        flavour="sic",
                        time_start=datetime(2025, 8, 13, 10, 0),
                        time_end=datetime(2025, 8, 13, 10, 1),
                        input=[],
                        response=[
                            GenericClassificationResult(
                                type="sic",
                                classified=True,
                                code="1234",
                                description="Example",
                                reasoning="Example reason",
                                candidates=[
                                    GenericCandidate(
                                        code="1234",
                                        descriptive="Some candidate",
                                        likelihood=0.9,
                                    )
                                ],
                                follow_up=FollowUp(
                                    questions=[
                                        FollowUpQuestion(
                                            id="f1",
                                            text="What do you do?",
                                            type="text",
                                            response="",
                                            select_options=None,
                                        )
                                    ]
                                ),
                            )
                        ],
                    )
                ],
            )
        ],
    )


@pytest.mark.utils
def test_add_follow_up_model_question(
    app,
    survey_result_with_followup_model: GenericSurveyAssistResult,
) -> None:
    """Successfully add follow up question to survey_result."""
    with app.test_request_context():
        save_model_to_session("survey_result", survey_result_with_followup_model)

        updated = add_follow_up_response_to_classify("f1", "New answer")

        response = updated.responses[0].survey_assist_interactions[0].response
        assert isinstance(response, list)
        result = response[0]
        assert result.follow_up is not None
        assert result.follow_up.questions[0].response == "New answer"


@pytest.mark.utils
def test_add_follow_up_no_matching_question_id(
    app,
    survey_result_with_followup_model: GenericSurveyAssistResult,
) -> None:
    """Unsuccessfully add follow up question to survey_result - no matching question_id."""
    with app.test_request_context():
        save_model_to_session("survey_result", survey_result_with_followup_model)

        with pytest.raises(
            ValueError, match="No follow-up question found with id=does-not-exist"
        ):
            add_follow_up_response_to_classify("does-not-exist", "irrelevant")


@pytest.mark.utils
def test_add_follow_up_no_classify_interaction(app) -> None:
    """Unsuccessfully add follow up question to survey_result - no interaction."""
    empty_result = GenericSurveyAssistResult(
        survey_id="test-survey",
        case_id="test-case",
        user="user.respondent-a",
        time_start=datetime(2025, 8, 13, 10, 0),
        time_end=datetime(2025, 8, 13, 10, 2),
        responses=[
            GenericResponse(
                person_id="user.respondent-a",
                time_start=datetime(2025, 8, 13, 10, 0),
                time_end=datetime(2025, 8, 13, 10, 1),
                survey_assist_interactions=[],  # no interactions
            )
        ],
    )

    with app.test_request_context():
        save_model_to_session("survey_result", empty_result)

        with pytest.raises(
            ValueError, match="No follow-up question found with id=anything"
        ):
            add_follow_up_response_to_classify("anything", "irrelevant")


@pytest.mark.utils
def test_add_follow_up_no_matching_person(
    app, survey_result_with_followup_model: GenericSurveyAssistResult
) -> None:
    """Unsuccessfully add follow up question to survey_result - person_id not found."""
    survey_result_with_followup_model.responses[0].person_id = "someone-else"

    with app.test_request_context():
        save_model_to_session("survey_result", survey_result_with_followup_model)

        with pytest.raises(ValueError, match="No responses for person_id=non-existent"):
            add_follow_up_response_to_classify("f1", "value", person_id="non-existent")
