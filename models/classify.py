"""Module that provides the models for the classification endpoint.

This module contains the request and response models for the classification endpoint.
It defines the structure of the data that can be sent to and received from the endpoint.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LLMModel(str, Enum):
    """Enum for LLM models."""

    CHAT_GPT = "chat-gpt"
    GEMINI = "gemini"


class ClassificationType(str, Enum):
    """Enum for classification types."""

    SIC = "sic"
    SOC = "soc"
    SIC_SOC = "sic_soc"


class ClassificationOptions(BaseModel):
    """Model for classification options.

    Attributes:
        sic (Optional[SICOptions]): SIC-specific classification options.
        soc (Optional[SOCOptions]): SOC-specific classification options.
    """

    sic: Optional["SICOptions"] = Field(
        None, description="SIC-specific classification options"
    )
    soc: Optional["SOCOptions"] = Field(
        None, description="SOC-specific classification options"
    )


class SICOptions(BaseModel):
    """Model for SIC-specific classification options.

    Attributes:
        rephrased (bool): Whether to apply rephrasing to SIC classification results.
            Defaults to True to maintain backward compatibility.
    """

    rephrased: bool = Field(
        default=True,
        description="Whether to apply rephrasing to SIC classification results",
    )


class SOCOptions(BaseModel):
    """Model for SOC-specific classification options.

    Attributes:
        rephrased (bool): Whether to apply rephrasing to SOC classification results.
            Defaults to True to maintain backward compatibility.
    """

    rephrased: bool = Field(
        default=True,
        description="Whether to apply rephrasing to SOC classification results",
    )


class ClassificationRequest(BaseModel):
    """Model for the classification request.

    Attributes:
        llm (LLMModel): The LLM model to use.
        type (ClassificationType): Type of classification.
        job_title (str): Survey response for Job Title.
        job_description (str): Survey response for Job Description.
        org_description (Optional[str]): Survey response for Organisation / Industry Description.
        options (Optional[ClassificationOptions]): Optional classification options.
    """

    llm: LLMModel
    type: ClassificationType
    job_title: str = Field(..., description="Survey response for Job Title")
    job_description: str = Field(..., description="Survey response for Job Description")
    org_description: Optional[str] = Field(
        None, description="Survey response for Organisation / Industry Description"
    )
    options: Optional[ClassificationOptions] = Field(
        None, description="Optional classification options"
    )


# New generic models for supporting both SIC and SOC classification
class GenericCandidate(BaseModel):
    """Model for a generic classification candidate.

    Attributes:
        code (str): The classification code.
        descriptive (str): The classification description.
        likelihood (float): The likelihood of the match.
    """

    code: str = Field(..., description="Classification code")
    descriptive: str = Field(..., description="Classification description")
    likelihood: float = Field(ge=0.0, le=1.0, description="Likelihood of match")


class GenericClassificationResult(BaseModel):
    """Model for a generic classification result.

    Attributes:
        type (str): The type of classification (sic, soc).
        classified (bool): Whether the input could be definitively classified.
        followup (Optional[str]): Additional question to help classify.
        code (Optional[str]): The classification code. Empty if classified=False.
        description (Optional[str]): The classification description. Empty if classified=False.
        candidates (list[GenericCandidate]): List of potential classification candidates.
        reasoning (str): Reasoning behind the LLM's response.
    """

    type: str = Field(..., description="Type of classification (sic, soc)")
    classified: bool = Field(
        ..., description="Could the input be definitively classified?"
    )
    followup: Optional[str] = Field(
        None, description="Additional question to help classify"
    )
    code: Optional[str] = Field(
        None, description="Classification code. Empty if classified=False"
    )
    description: Optional[str] = Field(
        None, description="Classification description. Empty if classified=False"
    )
    candidates: list[GenericCandidate] = Field(
        ..., description="List of potential classification candidates"
    )
    reasoning: str = Field(..., description="Reasoning behind the LLM's response")


class AppliedOptions(BaseModel):
    """Model for applied options in the response meta.

    Attributes:
        sic (dict): Applied SIC options.
        soc (dict): Applied SOC options.
    """

    sic: dict = Field(default_factory=dict, description="Applied SIC options")
    soc: dict = Field(default_factory=dict, description="Applied SOC options")


class ResponseMeta(BaseModel):
    """Model for response metadata.

    Attributes:
        llm (str): The LLM model used.
        applied_options (AppliedOptions): The options that were applied.
    """

    llm: str = Field(..., description="The LLM model used")
    applied_options: AppliedOptions = Field(
        ..., description="The options that were applied"
    )


class GenericClassificationResponse(BaseModel):
    """Model for the generic classification response.

    Attributes:
        requested_type (str): The type of classification that was requested.
        results (list[GenericClassificationResult]): List of classification results.
        meta (Optional[ResponseMeta]): Response metadata, only included when options were provided.
    """

    requested_type: str = Field(
        ..., description="Type of classification that was requested"
    )
    results: list[GenericClassificationResult] = Field(
        ..., description="List of classification results"
    )
    meta: Optional[ResponseMeta] = Field(
        default=None,
        description="Response metadata, only included when options were provided",
    )


class GenericClassificationResponseWithoutMeta(BaseModel):
    """Model for the generic classification response without meta field.

    Attributes:
        requested_type (str): The type of classification that was requested.
        results (list[GenericClassificationResult]): List of classification results.
    """

    requested_type: str = Field(
        ..., description="Type of classification that was requested"
    )
    results: list[GenericClassificationResult] = Field(
        ..., description="List of classification results"
    )
