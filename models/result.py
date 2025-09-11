"""Pydantic models for Survey Assist UI result data.

This module defines models for input fields, follow-up questions, classification results,
lookup responses, and survey assist interactions. All models are used to validate and
structure data exchanged between the Survey Assist UI and backend services.
"""

from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel, Field


class InputField(BaseModel):
    """Model for input field data.

    Attributes:
        field (str): The field name.
        value (str): The field value.
    """

    field: str = Field(..., description="The field name")
    value: str = Field(..., description="The field value")


class FollowUpQuestion(BaseModel):
    """Model for follow-up questions.

    Attributes:
        id (str): Question identifier.
        text (str): Question text.
        type (str): Question type, either 'text' or 'select'.
        select_options (Optional[list[str]]): Options for select type questions.
        response (str): User's response to the question.
    """

    id: str = Field(..., description="Question identifier")
    text: str = Field(..., description="Question text")
    type: str = Field(
        ..., description="Question type (text or select)", pattern="^(text|select)$"
    )
    select_options: Optional[list[str]] = Field(
        None, description="Options for select type questions"
    )
    response: str = Field(..., description="User's response to the question")


class FollowUp(BaseModel):
    """Model for follow-up data.

    Attributes:
        questions (list[FollowUpQuestion]): List of follow-up questions.
    """

    questions: list[FollowUpQuestion] = Field(
        ..., description="List of follow-up questions"
    )


class GenericCandidate(BaseModel):
    """Model for generic classification candidates that can be SIC or SOC.

    Attributes:
        code (str): The classification code.
        descriptive (str): The classification description.
        likelihood (float): Confidence score between 0 and 1.
    """

    code: str = Field(..., description="The classification code")
    descriptive: str = Field(..., description="The classification description")
    likelihood: float = Field(..., description="Confidence score between 0 and 1")


class GenericClassificationResult(BaseModel):
    """Model for generic classification result that can be SIC or SOC.

    Attributes:
        type (str): Type of classification (sic, soc).
        classified (bool): Whether the input was classified.
        follow_up (Optional[FollowUp]): Follow-up question if needed.
        code (Optional[str]): The classification code.
        description (Optional[str]): The classification description.
        candidates (list[GenericCandidate]): List of potential classifications.
        reasoning (str): Reasoning behind the classification.
    """

    type: str = Field(..., description="Type of classification (sic, soc)")
    classified: bool = Field(..., description="Whether the input was classified")
    follow_up: Optional[FollowUp] = Field(
        None, description="Follow-up question if needed"
    )
    code: Optional[str] = Field(None, description="The classification code")
    description: Optional[str] = Field(
        None, description="The classification description"
    )
    candidates: list[GenericCandidate] = Field(
        ..., description="List of potential classifications"
    )
    reasoning: str = Field(..., description="Reasoning behind the classification")


class PotentialDivision(BaseModel):
    """Model for potential division data.

    Attributes:
        code (str): The division code.
        title (str): The division title.
        detail (Optional[str]): Additional division details.
    """

    code: str = Field(..., description="The division code")
    title: str = Field(..., description="The division title")
    detail: Optional[str] = Field(None, description="Additional division details")


class PotentialCode(BaseModel):
    """Model for potential code data.

    Attributes:
        code (str): The code.
        description (str): The code description.
    """

    code: str = Field(..., description="The code")
    description: str = Field(..., description="The code description")


class LookupResponse(BaseModel):
    """Model for lookup response.

    Attributes:
        found (bool): Whether matches were found.
        code (str): The matched code.
        code_division (str): The matched code division.
        potential_codes_count (int): Number of potential codes found.
        potential_divisions (list[PotentialDivision]): List of potential divisions.
        potential_codes (list[PotentialCode]): List of potential codes.
    """

    found: bool = Field(..., description="Whether matches were found")
    code: Optional[str] = Field(None, description="The matched code")
    code_division: Optional[str] = Field(None, description="The code division")
    potential_codes_count: int = Field(
        ..., description="Number of potential codes found"
    )
    potential_divisions: list[PotentialDivision] = Field(
        ..., description="List of potential divisions"
    )
    potential_codes: list[PotentialCode] = Field(
        ..., description="List of potential codes"
    )


class GenericSurveyAssistInteraction(BaseModel):
    """Model for generic survey assist interaction that can handle SIC or SOC.

    Attributes:
        type (str): Interaction type (classify or lookup).
        flavour (str): Classification flavour (sic, soc, or sic_soc).
        time_start (datetime): Start time of the interaction.
        time_end (datetime): End time of the interaction.
        input (list[InputField]): Input data for the interaction.
        response (Union[list[GenericClassificationResult], LookupResponse]):
            Response from the interaction.
    """

    type: str = Field(
        ...,
        description="Interaction type (classify or lookup)",
        pattern="^(classify|lookup)$",
    )
    flavour: str = Field(
        ...,
        description="Classification flavour (sic, soc, or sic_soc)",
        pattern="^(sic|soc|sic_soc)$",
    )
    time_start: datetime = Field(..., description="Start time of the interaction")
    time_end: datetime = Field(..., description="End time of the interaction")
    input: list[InputField] = Field(..., description="Input data for the interaction")
    response: Union[list[GenericClassificationResult], LookupResponse] = Field(
        ..., description="Response from the interaction"
    )


class GenericResponse(BaseModel):
    """Model for a single generic response that can handle SIC or SOC.

    Attributes:
        person_id (str): Identifier for the person.
        time_start (datetime): Start time of the response.
        time_end (datetime): End time of the response.
        survey_assist_interactions (list[GenericSurveyAssistInteraction]):
            List of survey assist interactions.
    """

    person_id: str = Field(..., description="Identifier for the person")
    time_start: datetime = Field(..., description="Start time of the response")
    time_end: datetime = Field(..., description="End time of the response")
    survey_assist_interactions: list[GenericSurveyAssistInteraction] = Field(
        ..., description="List of survey assist interactions"
    )


class GenericSurveyAssistResult(BaseModel):
    """Model for the complete generic survey assist result that can handle SIC or SOC.

    Attributes:
        survey_id (str): Identifier for the survey.
        case_id (str): Identifier for the case.
        user (str): User identifier in format 'name.surname'.
        time_start (datetime): Start time of the survey.
        time_end (datetime): End time of the survey.
        responses (list[GenericResponse]): List of responses.
    """

    survey_id: str = Field(
        ..., description="Identifier for the survey", examples=["test-survey-123"]
    )
    case_id: str = Field(
        ..., description="Identifier for the case", examples=["test-case-456"]
    )
    user: str = Field(
        ...,
        description="User identifier in format 'name.surname'",
        examples=["test.userSA187"],
    )
    time_start: datetime = Field(
        ..., description="Start time of the survey", examples=["2024-03-19T10:00:00Z"]
    )
    time_end: datetime = Field(
        ..., description="End time of the survey", examples=["2024-03-19T10:05:00Z"]
    )
    responses: list[GenericResponse] = Field(..., description="List of responses")


class ResultResponse(BaseModel):
    """Response model for result endpoints.

    Attributes:
        message (str): Response message.
        result_id (Optional[str]): Unique identifier for the stored result.
    """

    message: str = Field(..., description="Response message")
    result_id: Optional[str] = Field(
        None, description="Unique identifier for the stored result"
    )
