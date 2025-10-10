"""Utility functions for Flask application to map results structures.

This module provides helper functions for mapping results.
Internally the data is stored to accomodate SIC, SOC and Lookup results,
it needs to be translated to the API format which only supports SIC and
Lookup results.
"""

from __future__ import annotations

from typing import Any

from models.result_sic_only import (
    Candidate,
    ClassificationResponse,
    FollowUp,
    FollowUpQuestion,
    InputField,
    LookupResponse,
    PotentialCode,
    PotentialDivision,
    Response,
    SurveyAssistInteraction,
    SurveyAssistResult,
)


def _map_follow_up(fu: dict[str, Any] | None) -> FollowUp | None:
    """Convert a follow-up dictionary to a FollowUp model.

    Args:
        fu (dict[str, Any] | None): The follow-up dictionary or None.

    Returns:
        FollowUp | None: The FollowUp model or None if input is None.
    """
    if not fu:
        return None
    return FollowUp(
        questions=[
            FollowUpQuestion(
                id=q["id"],
                text=q["text"],
                type=q["type"],
                select_options=(q.get("select_options") or None),
                response=q["response"],
            )
            for q in fu.get("questions", [])
        ]
    )


def _map_candidates(cands: list[dict[str, Any]]) -> list[Candidate]:
    """Convert a list of candidate dictionaries to Candidate models.

    Args:
        cands (list[dict[str, Any]]): List of candidate dictionaries.

    Returns:
        list[Candidate]: List of Candidate models.
    """
    return [
        Candidate(
            code=c["code"],
            description=c.get("description") or c.get("descriptive") or "",
            likelihood=float(c["likelihood"]),
        )
        for c in cands
    ]


def _map_classify_response(resp_list: list[dict[str, Any]]) -> ClassificationResponse:
    """Convert a list of classification response dicts to a ClassificationResponse model.

    Args:
        resp_list (list[dict[str, Any]]): List of classification response dicts.

    Returns:
        ClassificationResponse: The mapped ClassificationResponse model.

    Raises:
        ValueError: If the response list does not contain exactly one item.
    """
    if len(resp_list) != 1:
        raise ValueError(
            f"Expected exactly one classification response, got {len(resp_list)}"
        )

    chosen = resp_list[0]
    return ClassificationResponse(
        classified=bool(chosen["classified"]),
        code=chosen["code"],
        description=chosen["description"],
        reasoning=chosen.get("reasoning", ""),
        candidates=_map_candidates(chosen.get("candidates", [])),
        follow_up=_map_follow_up(chosen.get("follow_up")) or FollowUp(questions=[]),
    )


def _map_lookup_response(resp: dict[str, Any]) -> LookupResponse:
    """Convert a lookup response dictionary to a LookupResponse model.

    Args:
        resp (dict[str, Any]): The lookup response dictionary.

    Returns:
        LookupResponse: The mapped LookupResponse model.
    """
    return LookupResponse(
        found=bool(resp["found"]),
        code=resp.get("code"),
        code_division=resp.get("code_division"),
        potential_codes_count=int(resp.get("potential_codes_count", 0)),
        potential_divisions=[
            PotentialDivision(
                code=d["code"],
                title=d["title"],
                detail=d.get("detail"),
            )
            for d in resp.get("potential_divisions", [])
        ],
        potential_codes=[
            PotentialCode(
                code=c["code"],
                description=c["description"],
            )
            for c in resp.get("potential_codes", [])
        ],
    )


ResponseModel = ClassificationResponse | LookupResponse


def _map_interaction(it: dict[str, Any]) -> SurveyAssistInteraction:
    """Convert an interaction dictionary to a SurveyAssistInteraction model.

    Args:
        it (dict[str, Any]): The interaction dictionary.

    Returns:
        SurveyAssistInteraction: The mapped SurveyAssistInteraction model.
    """
    it_type = it["type"]  # "classify" | "lookup"
    flavour = it["flavour"]
    response_obj: ResponseModel

    inputs = [
        InputField(field=i["field"], value=i["value"]) for i in it.get("input", [])
    ]

    if it_type == "classify":
        response_obj = _map_classify_response(it.get("response", []))
    else:
        response_obj = _map_lookup_response(it.get("response", {}))

    return SurveyAssistInteraction(
        type=it_type,
        flavour=flavour,
        time_start=it["time_start"],
        time_end=it["time_end"],
        input=inputs,
        response=response_obj,
    )


def translate_session_to_model(session: dict[str, Any]) -> SurveyAssistResult:
    """Translate the internal `survey_result` dict into a `SurveyAssistResult` model.

    Args:
        session (dict[str, Any]): The session dictionary containing survey results.

    Returns:
        SurveyAssistResult: The mapped SurveyAssistResult model.
    """
    sr = session.get("survey_result", session)

    return SurveyAssistResult(
        survey_id=sr["survey_id"],
        wave_id=sr["wave_id"],
        case_id=sr["case_id"],
        user=sr["user"],
        time_start=sr["time_start"],
        time_end=sr["time_end"],
        responses=[
            Response(
                person_id=r["person_id"],
                time_start=r["time_start"],
                time_end=r["time_end"],
                survey_assist_interactions=[
                    _map_interaction(it)
                    for it in r.get("survey_assist_interactions", [])
                ],
            )
            for r in sr.get("responses", [])
        ],
    )
