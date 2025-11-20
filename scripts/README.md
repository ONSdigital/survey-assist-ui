# UI Log Analysis Script

This directory contains the CLI tool `ui_log_analysis.py` used to analyse UI survey
logs. It extracts structured events (core questions, dynamic follow ups, SIC lookup
status, classification outcomes, routing, and data store events) and can produce per
person summaries.

## Features

* Parses core question responses ("saved response for <question>").
* Detects dynamic follow up question tokens (`survey_assist_followup_<n>`).
* Captures SIC lookup status (match / not matched classify).
* Captures classification status (classified unambiguously / not classified followup).
* Notes routing events (rerouted no employment).
* Records survey and feedback persistence (IDs when present).
* Outputs JSON Lines (JSONL) events or a consolidated summary.

## Obtaining Logs from GCP

Run the following command to pull Cloud Run logs and write them to a local file. Replace
`SERVICE-NAME`, `YYYY-MM-DDTHH:MM:SSZ`, `GCP_PROJECT_ID`, and `<date-time>`.

```bash
gcloud logging read \
	'resource.type="cloud_run_revision"\n   AND resource.labels.service_name="SERVICE-NAME"\n   AND timestamp >= "YYYY-MM-DDTHH:MM:SSZ"' \
	--format='value(textPayload)' \
	--project=GCP_PROJECT_ID > ui-log-<date-time>.log
```

Example output
```json
[
  {
    "person_id": "UNIQUE-ID",
    "core_questions": [
      "age_range",
      "job_description",
      "job_title",
      "organisation_activity_question",
      "organisation_type",
      "other-feedback",
      "paid_job",
      "survey-comfort",
      "survey-ease",
      "survey-relevance"
    ],
    "dynamic_questions": [
      "survey_assist_followup_1",
      "survey_assist_followup_2"
    ],
    "sic_lookup_statuses": [
      "not_matched_classify"
    ],
    "classification_statuses": [
      "not_classified_followup"
    ],
    "rerouted_no_employment": false,
    "survey_results_saved": 1,
    "feedback_results_saved": 1,
    "survey_result_ids": [
      "uniquesurveyresultid"
    ],
    "feedback_result_ids": [
      "uniquefeedbackresultid"
    ]
  }
]
```


Notes:
* You can widen or narrow the time window by adjusting the timestamp clause.
* Ensure you have `gcloud auth login` and correct project permissions.
* Do not commit raw log files to the repository.

## Installing / Environment

The project uses Poetry. Ensure dependencies are installed:

```bash
poetry install
```

## Basic Usage

Stream events (JSONL) from a saved log file:

```bash
poetry run python scripts/ui_log_analysis.py ui-log-20-Nov-09:00.log
```

Produce a per person summary (single JSON document):

```bash
poetry run python scripts/ui_log_analysis.py ui-log-20-Nov-09:00.log --summary
```

Read from stdin (useful when piping directly from gcloud):

```bash
gcloud logging read 'resource.type="cloud_run_revision" ...' --format='value(textPayload)' \
	--project=GCP_PROJECT_ID | \
	poetry run python scripts/ui_log_analysis.py - --summary
```

## Output Schema

Event JSONL fields:
* `person_id`: Identifier extracted from log line.
* `kind`: One of core, dynamic, sic_lookup, classification, routing, survey_saved, feedback_saved.
* `question`: Present for core or dynamic question events.
* `status`: Present for status style events (e.g. classified_unambiguously).
* `document_id`: Present when a survey or feedback result ID is captured.
* `raw`: Original log line for traceability.

Summary JSON fields (per person):
* `core_questions`: Sorted list of answered core questions.
* `dynamic_questions`: Sorted list of dynamic follow up questions.
* `sic_lookup_statuses`: Distinct statuses seen during SIC lookups.
* `classification_statuses`: Distinct classification statuses.
* `rerouted_no_employment`: True if routing event occurred.
* `survey_results_saved` / `feedback_results_saved`: Counts of persistence events.
* `survey_result_ids` / `feedback_result_ids`: Collected document IDs.

## Tips

* To filter for one person: `grep 'person_id:ABC123' ui-log-*.log | poetry run python \
	scripts/ui_log_analysis.py - --summary`.
* Pipe JSONL into `jq` for ad hoc analysis.
* Combine multiple logs: `cat ui-log-*.log | poetry run python scripts/ui_log_analysis.py -`.
