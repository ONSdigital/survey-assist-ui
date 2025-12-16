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

Notes:
* You can widen or narrow the time window by adjusting the timestamp clause.
* Ensure you have `gcloud auth login` and correct project permissions.
* **Do not commit raw log files to the repository.**

## Installing / Environment

The project uses Poetry. Ensure dependencies are installed:

```bash
poetry install
```

## Basic Usage

Read from stdin (useful when piping directly from gcloud):

```bash
gcloud logging read 'resource.type="cloud_run_revision" ...' --format='value(textPayload)' \
	--project=GCP_PROJECT_ID | \
	poetry run python scripts/ui_log_analysis.py - --summary
```

Stream events (JSONL) from a saved log file:

```bash
poetry run python scripts/ui_log_analysis.py ui-log-20-Nov-09:00.log
```

Produce a per person summary (single JSON document):

```bash
poetry run python scripts/ui_log_analysis.py ui-log-20-Nov-09:00.log --summary
```

Example output
```json
[
  {
    "person_id": "UNIQUE-ID",
    "access_time": "2025-12-01T08:44:07.556432297Z",
    "core_questions": [
      {
        "question": "age_range",
        "timestamp": "2025-12-01T08:44:21.582332185Z"
      },
      {
        "question": "job_description",
        "timestamp": "2025-12-01T08:46:15.933209320Z"
      },
      {
        "question": "job_title",
        "timestamp": "2025-12-01T08:44:39.080396244Z"
      },
      {
        "question": "organisation_activity_question",
        "timestamp": "2025-12-01T08:47:31.216112666Z"
      },
      {
        "question": "organisation_type",
        "timestamp": "2025-12-01T08:50:04.123971700Z"
      },
      {
        "question": "other-feedback",
        "timestamp": "2025-12-01T08:50:35.557082880Z"
      },
      {
        "question": "paid_job",
        "timestamp": "2025-12-01T08:44:26.577446134Z"
      },
      {
        "question": "survey-comfort",
        "timestamp": "2025-12-01T08:50:25.228576644Z"
      },
      {
        "question": "survey-ease",
        "timestamp": "2025-12-01T08:50:15.273007382Z"
      },
      {
        "question": "survey-relevance",
        "timestamp": "2025-12-01T08:50:21.060611980Z"
      }
    ],
    "dynamic_questions": [
      {
        "question": "survey_assist_followup_1",
        "timestamp": "2025-12-01T08:49:44.529913907Z"
      },
      {
        "question": "survey_assist_followup_2",
        "timestamp": "2025-12-01T08:49:45.047712994Z"
      }
    ],
    "sic_lookup_statuses": [
      {
        "status": "not_matched_classify",
        "timestamp": "2025-12-01T08:47:35.317408689Z"
      }
    ],
    "classification_statuses": [
      {
        "status": "not_classified_followup",
        "timestamp": "2025-12-01T08:47:44.390968853Z"
      }
    ],
    "rerouted_no_employment": false,
    "survey_results_saved": 1,
    "feedback_results_saved": 1,
    "survey_result_ids": [
      {
        "id": "ExAmPleLaCZf5fQGVWsn08",
        "timestamp": "2025-12-01T08:50:05.757552656Z"
      }
    ],
    "feedback_result_ids": [
      {
        "id": "CQXUZD0ExAmPleM1PU",
        "timestamp": "2025-12-01T08:50:36.747752676Z"
      }
    ],
    "dynamic_question_texts": [
      {
        "question": "What is the main purpose of your organisation's building restoration work?",
        "timestamp": "2025-12-01T08:47:44.390968853Z"
      }
    ],
    "classification_code": "",
    "unsuccessful_access": false
  },
]
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
* `classification_code` : The code that was selected when a succesful SIC lookup or unambiguous match was made.
* `unsuccessful_access` : Indicates if the person_id had an unsuccessful login attempt.

## Tips

* To filter for one person: `grep 'person_id:ABC123' ui-log-*.log | poetry run python \
	scripts/ui_log_analysis.py - --summary`.
* Pipe JSONL into `jq` for ad hoc analysis.
* Combine multiple logs: `cat ui-log-*.log | poetry run python scripts/ui_log_analysis.py -`.

## Combining Scripts

The ui_log_analysis.py script is the core script for extracting data from the logs for Survey Assist, but combining the output it produces with the following scripts provides further insight into how users have interacted. 

### Run the analyse log script

See the instructions above on getting the logs from a certain date and creating a file with the output.  For the following examples we assume the output from the ui_log_analysis.py script is **ui-log-DD-MM-HH:MM.log**

### Create a json file from the logs

```bash
poetry run python scripts/ui_log_analysis.py ui-log-24-Nov-15:30.log --summary > ui-log-DD-MM-HH:MM.json
```

This generates a list of json objects in **ui-log-DD-MM-HH:MM.json**

### Users that were unable access the survey

The output from the ui_log_analysis.py --summary script will give insight to those users that tried to access the survey but failed.

Unsuccessful access and core questions not asked and survey or feedback not saved:

```bash
jq '[
      .[]
      | select(
            .unsuccessful_access == true
            and (.core_questions | length == 0)
            and .survey_results_saved == 0
            and .feedback_results_saved == 0
        )
    ] as $matches
    | {
        count: ($matches | length),
        users: $matches
      }' ui-log-DD-MM-HH:DD.json > ui-log-DD-MM-HH:MM-access-issues.json

[
  {
    "person_id": "QS2F-01",
    "access_time": "",
    "core_questions": [],
    "dynamic_questions": [],
    "sic_lookup_statuses": [],
    "classification_statuses": [],
    "rerouted_no_employment": false,
    "survey_results_saved": 0,
    "feedback_results_saved": 0,
    "survey_result_ids": [],
    "feedback_result_ids": [],
    "dynamic_question_texts": [],
    "classification_code": "",
    "unsuccessful_access": true
  },
  {
    "person_id": "V4EZ-01",
    "access_time": "",
    "core_questions": [],
    "dynamic_questions": [],
    "sic_lookup_statuses": [],
    "classification_statuses": [],
    "rerouted_no_employment": false,
    "survey_results_saved": 0,
    "feedback_results_saved": 0,
    "survey_result_ids": [],
    "feedback_result_ids": [],
    "dynamic_question_texts": [],
    "classification_code": "",
    "unsuccessful_access": true
  },
  ...
```

Unsuccessful access but managed to access in the end and save a result:

```bash
jq '[
      .[]
      | select(
            .unsuccessful_access == true
            and (.survey_results_saved == 1    
            or .feedback_results_saved == 1)
        )
    ] as $matches
    | {
        count: ($matches | length),
        users: $matches
      }' ui-log-DD-MM-HH:MM.json > ui-log-DD-MM-HH:MM-access-issues-saved-result.json
```

Users that had access issues, managed to access the survey but abandoned after being asked a question:

```bash
jq '[                                                  
      .[]                         
      | select(
            .unsuccessful_access == true
            and (.core_questions | length != 0)
            and .survey_results_saved == 0  
            and .feedback_results_saved == 0
        )
    ] as $matches
    | {
        count: ($matches | length),
        users: $matches
      }' ui-log-DD-MM-HH:MM.json > ui-log-DD-MM-HH:MM-access-issues-abandoned.json
```


### Determine the time each user spent and their flow through the survey

The ui_time_spent.py script will parse the objects from the ui_log_analysis.py script and create a list of json that details times for each user and an overview of the journey the user made.  Run this against the ui_log_analysis.py --summary script output.

```bash
poetry run python scripts/ui_time_spent.py ui-log-DD-MM-HH:MM.json > DD-MM-HH-MM.txt
```

Example output
```bash
{
    "person_id": "STP01234-01",
    "access_time": "2025-12-01T10:04:54.323530879Z",
    "end_time": "2025-12-01T10:07:37.540316657Z",
    "total_survey_time": "00:02:43",
    "journey_type": "full_journey",
    "overview": "sic_lookup_success",
    "last_event": "feedback_result_saved"
  },
```

### Use jQuery to get high level numbers

Using the output from the ui_time_spent.py script, jQuery can provide some high level numbers about the survey participation.

Number of objects:

```bash
jq length  DD-MM-HH-MM.txt
696
```

Number of users that completed a full journey (answered survey and provided feedback):

```bash
jq '[.[] | select(.journey_type == "full_journey")] | length' DD-MM-DD-MM.txt
450
```

Number of users that only completed the survey section:

```bash
jq '[.[] | select(.journey_type == "survey_only")] | length' DD-MM-DD-MM.txt
100
```

Number of users that were not in employment:

```bash
jq '[.[] | select(.overview == "not_in_employment")] | length' DD-MM-DD-MM.txt
25
```

Number of users that were unambiguously classified without the need for a follow up question by Survey Assist:

```bash
jq '[.[] | select(.overview == "unambiguous_classification")] | length' DD-MM-DD-MM.txt
```

Number of users that were asked a dynamic follow up question by Survey Assist:

```bash
jq '[.[] | select(.overview == "dynamic_question_needed")] | length' DD-MM-DD-MM.txt
```

Number of users that were classified by a well known SIC knowledgebase lookup by Survey Assist:

```bash
jq '[.[] | select(.overview == "sic_lookup_success")] | length' DD-MM-DD-MM.txt
```

Number of users that were asked a survey question but did not get to the point where Survey Assist was interacted with:

```bash
jq '[.[] | select(.overview == "did_not_reach_classification")] | length' DD-MM-DD-MM.txt
```

Note: These are users that have either abandoned after being asked a survey question or were part way through the survey when the logs were gathered. 


Number of users that were asked a survey question but did not save a survey response yet.  This number will include the users that are reported as "did_not_reach_classification" plus any users that abandoned after that point.

```bash
jq '[.[] | select(.journey_type == "abandoned")] | length' DD-MM-DD-MM.txt
```

Note: These are users that have either abandoned the survey or were part way through the survey when the logs were gathered. 

### Calculate average times and create a timeseries of interactions

The ui_avg_journey_time.py will calculate the average times users spent in the UI either answering just the survey section or both the survey and feedback section. As well as the average times, the longest and shortest journey are calculated too.

This script also creates an array of interactions per hour which can be used to plot a graph of enagaement (see later step).

```bash
poetry run python scripts/ui_avg_journey_time.py DD-MM-HH-MM.txt > avg-time-DD-MM-HH-MM.txt
```

Example output:

```json
{
  "full_journey": {
    "average": {
      "seconds": 998,
      "hms": "00:16:38"
    },
    "longest": {
      "seconds": 329621,
      "hms": "91:33:41",
      "person_id": "STP04321-01"
    },
    "shortest": {
      "seconds": 75,
      "hms": "00:01:15",
      "person_id": "STP12345-01"
    }
  },
  "survey_only": {
    "average": {
      "seconds": 136,
      "hms": "00:02:16"
    },
    "longest": {
      "seconds": 4220,
      "hms": "01:10:20",
      "person_id": "STP09999-01"
    },
    "shortest": {
      "seconds": 11,
      "hms": "00:00:11",
      "person_id": "STP66666-01"
    }
  },
  "timeseries": [
    {
      "date": "2025-11-24",
      "hour": 15,
      "total": 38,
      "full_journey_count": 29,
      "survey_only_count": 5
    },
    {
      "date": "2025-11-24",
      "hour": 16,
      "total": 39,
      "full_journey_count": 32,
      "survey_only_count": 6
    },
    {
      "date": "2025-11-24",
      "hour": 17,
      "total": 23,
      "full_journey_count": 17,
      "survey_only_count": 3
    },
    {
      "date": "2025-11-24",
      "hour": 18,
      "total": 10,
      "full_journey_count": 7,
      "survey_only_count": 1
    },
    {
      "date": "2025-11-24",
      "hour": 19,
      "total": 12,
      "full_journey_count": 8,
      "survey_only_count": 1
    },
    {
      "date": "2025-11-24",
      "hour": 20,
      "total": 6,
      "full_journey_count": 5,
      "survey_only_count": 1
    },
    {
      "date": "2025-11-24",
      "hour": 21,
      "total": 11,
      "full_journey_count": 10,
      "survey_only_count": 0
    },
    {
      "date": "2025-11-24",
      "hour": 22,
      "total": 2,
      "full_journey_count": 1,
      "survey_only_count": 1
    },
  ]
}
```

### Generate a graph of access over time

Output from the ui_avg_journey_time.py script can be parsed using the ui_time_spent.py script to create a graph of survey access and journey type for each hour the survey was active.

Create the timeseries data:

```bash
poetry run python scripts/ui_avg_journey_time.py DD-MM-HH-MM.txt > avg-time-DD-MM-HH-MM.txt
```

Convert to a graph and output as png:

```bash
poetry run python scripts/plot_timeseries.py avg-time-DD-MM-HH-MM.txt --output DD-MM-DD-MM.png
```

### Create a list of users that abandoned the journey and what the last event recorded was

Using the script ui_abandoned_jorney.py a list of users who were asked a question but did not save the survey can be compiled.

This list is useful for showing where in the survey a user's journey ended.

```bash
poetry run python scripts/ui_abandoned_journey.py DD-MM-HH-MM.txt > abandoned-DD-MM-HH-MM.txt
```

**Note**: The last_event captures the last recorded event in the logs, in most cases this captures the last question that was answered which means the question where the user abandoned would be the one after the recorded last_evet.  E.g if the last_event is recorded as job_title then the user likely saw the Job Description question but failed to answer it.

Example output:

```json
{
  "latest_end_time": "2025-12-01T12:36:02.306508Z",
  "abandoned_count": 37,
  "abandoned_users": [
    {
      "person_id": "STP021212-01",
      "access_time": "2025-11-29T17:07:49.950503122Z",
      "end_time": "2025-11-29T17:09:30.887396413Z",
      "total_survey_time": "00:01:40",
      "journey_type": "abandoned",
      "overview": "dynamic_question_needed",
      "last_event": "What is your employer's main method of providing telecommunications services?"
    },
    {
      "person_id": "STP91919-01",
      "access_time": "2025-12-01T00:00:50.429915691Z",
      "end_time": "2025-12-01T00:01:33.999324401Z",
      "total_survey_time": "00:00:43",
      "journey_type": "abandoned",
      "overview": "did_not_reach_classification",
      "last_event": "job_title"
    },
    {
      "person_id": "STP60606-01",
      "access_time": "2025-11-30T14:06:13.526756443Z",
      "end_time": "2025-11-30T14:16:20.033020477Z",
      "total_survey_time": "00:10:06",
      "journey_type": "abandoned",
      "overview": "did_not_reach_classification",
      "last_event": "job_description"
    },
    ...
  ]
}
```

### Get a list of the dynamic questions that were asked

Using the output from the ui_log_anaysis.py script and jQuery we can get a json structure of the users that were asked a dynamic question and what the question was.

```bash
jq '
  .[]
  | select(.dynamic_question_texts | length > 0)
  | . as $root
  | .dynamic_question_texts[]
  | select(.question != null and .timestamp != null)
  | {
      person_id: $root.person_id,
      access_time: $root.access_time,
      question_text: .question
    }
' ui-log-DD-MM-HH:MM.json > questions-DD-MM-HH:MM.json
```

Example output:

```json
{
  "person_id": "STP01111-01",
  "access_time": "2025-12-01T06:32:03.367196385Z",
  "question_text": "What age range of children does your organisation primarily educate?"
}
{
  "person_id": "STP02222-01",
  "access_time": "2025-11-30T23:38:31.349852307Z",
  "question_text": "What type of venue does your employer mainly operate?"
}
{
  "person_id": "STP03333-01",
  "access_time": "2025-11-30T21:49:48.888736871Z",
  "question_text": "What is your organisation's main activity or purpose?"
}
```

### Drop off

To get a list of all the places where a journey was abandoned (i.e the user accessed successfully but didn’t save a survey result) and the count of each unique individual user that dropped out, run:

```bash
jq '
  [ .[]
    | select(.journey_type == "abandoned" and .access_time != "")
  ]
  | group_by(.last_event)
  | map({
      last_event: (.[0].last_event),
      count: length
    })
' DD-MM-HH:MM-timespent-output.json > DD-MM-HH:MM-abandoned-counts-by-last-event.json
```

**Important** - in the generated output when last_event is populated this is the last event the user engaged with (i.e answered), so the point they dropped off is the next event in the flow.

last_event = ““ - indicates the user dropped out at the index “/”, “/intro” or age range question page before answering any questions.

last_event = “age_range“ - indicates the user dropped out at the paid_job “were you in employment” question.

last_event = “paid_job“ - indicates the user dropped out at the job_title “what is your job title” question.

last_event = “job_title“ - indicates the user dropped out at the job_desc “describe what you do in your job” question.

last_event = “job_description“ - indicates the user dropped out at the org_desc “describe the main activity of your organisation” question.

last_event = “organisation_activity_question“ - indicates the user dropped out at the closed organisation_type “describe the type of organisation” question after being unambiguously classified.

last_event = “survey_assist_followup_2” - indicates the user dropped out at the second follow up question presented by Survey Assist without answering

last_event = “An actual text question returned by Survey Assist“ - indicates the user dropped out at the Survey Assist interaction when questions were generated.

Example Output:

```json
[
  {
    "last_event": "",
    "count": 16
  },
  ...
  {
    "last_event": "What types of goods does your employer mainly sell?",
    "count": 1
  },
  {
    "last_event": "age_range",
    "count": 1
  },
  {
    "last_event": "job_description",
    "count": 11
  },
  {
    "last_event": "job_title",
    "count": 21
  },
  {
    "last_event": "organisation_activity_question",
    "count": 2
  },
  {
    "last_event": "paid_job",
    "count": 11
  },
  {
    "last_event": "survey_assist_followup_2",
    "count": 9
  }
]
```

#### Drop off before answering a question (index, intro guidance or age question drop off)

The users accessed the solution and then did not answer the first age range question, they could have dropped at the intro or index page or when the first question was presented.

```json
{
  "last_event": "",
  "count": 16
},
```

#### Drop off at the ‘Did you have a paid job…’ question (paid job drop off)

Remember the last event is the last question _answered_.

```json
{
    "last_event": "age_range",
    "count": 1
},
```

#### Drop off at the ‘What is the exact job title… ’ question (job title drop off)

```json
{
  "last_event": "paid_job",
  "count": 11
},
```

#### Drop off at the 'Describe what you do in that job…' question (job description drop off)

```json
{
  "last_event": "job_title",
  "count": 21
},
```

#### Drop off at the 'At your main job, describe the main activity of the business' question (organisation description drop off)

```json
{
  "last_event": "job_description",
  "count": 11
},
```

#### Drop off at the ‘What kind of organisation was it?’ question (organisation type drop off after unambiguous classification)

The instances of users that abandoned with this event show "overview": "unambiguous_classification"

```json
{
  "last_event": "organisation_activity_question",
  "count": 2
},
```

#### Drop off at dynamic questions (during Survey Assist serving follow up questions)

Count the number of entries with an actual question as last event, e.g:

```json
{
  "last_event": "What types of goods does your employer mainly sell?",
  "count": 1
},
```

#### Drop off at last dynamic question (during second follow up question)

```json
{
  "last_event": "survey_assist_followup_2",
  "count": 9
}
```

#### Drop off during feedback section

To get this we need to look at the users that completed the survey_only section

```bash
jq '[ .[] | select(.journey_type == "survey_only") ] | length' DD-MM-HH:MM-timespent-output.json  
178
```

#### Drop off trying or after accessing the solution

```bash
jq '
  [ .[]
    | select(.journey_type == "abandoned")
  ]
  | length ' DD-MM-HH:MM-timespent-output.json
218
```

#### Drop off before accessing the solution

```bash
jq '
  [ .[]
    | select(.journey_type == "abandoned" and .access_time == "")
  ]
  | length ' 08-Dec-15:30-timespent-output.json
132
```

### Average times for Survey Assist interactions

#### Dynamic questions asked

For those users that were asked a dynamic question the **ui_avg_survey_assist_time.py** script computes the time delta between the organisation activity question and the organisation type question (the time to see and respond to Survey Assist generated questions) and the difference between the organisation activity question and the display of the first dynamic question (the interaction time to do SIC lookup and a classify interaction involving two LLM interactions).

```bash
poetry run python scripts/ui_avg_survey_assist_time.py ui-log-DD-MM-HH:MM.json > time-in-survey-assist-DD-MM-HH:MM.json
```

Example output:

```json
{
  "not_classified_followup": {
    "users": [
      {
        "person_id": "STP22781-01",
        "time_in_seconds": 59,
        "time_to_show_dynamic_question": 10
      },
      {
        "person_id": "STP23212-01",
        "time_in_seconds": 63,
        "time_to_show_dynamic_question": 10
      },
      ...
    ],
    "summary": {
      "time_org_activity_to_org_type": {
        "count": 570,
        "average": 687,
        "average_excl_min_max": 109,
        "longest": 329531,
        "shortest": 23
      },
      "time_org_activity_to_dynamic_question": {
        "count": 570,
        "average": 8,
        "average_excl_min_max": 8,
        "longest": 16,
        "shortest": 5
      }
    }
  },
  ...
}
```

#### Classified unambiguously by LLM

Output is available from running the same **ui_avg_survey_assist_time.py** script:

```bash
poetry run python scripts/ui_avg_survey_assist_time.py ui-log-DD-MM-HH:MM.json > time-in-survey-assist-DD-MM-HH:MM.json
```

Example output:

```json
"classified_unambiguously": {
    "users": [
      {
        "person_id": "STP24891-01",
        "time_in_seconds": 43
      },
      {
        "person_id": "STP24893-01",
        "time_in_seconds": 21
      },
      ...
    ],
    "summary": {
      "time_org_activity_to_org_type": {
        "count": 359,
        "average": 958,
        "average_excl_min_max": 41,
        "longest": 329531,
        "shortest": 10
      }
    }
  }
```

### Activity by user id blocks

For analysis on what blocks of user ids were most active over time the summary output can be used to generate a list of well-formatted IDs.
The following command assumes the ONS ID format was STPnnnnn (where n is any numeric)
```bash
jq -r '
  # Normalise each object by adding .clean_id
  map(. + { clean_id: (.person_id | sub("-01$"; "")) })
  # Keep only valid STPnnnnn clean IDs
  | map(select(.clean_id | test("^STP[0-9]{5}$")))
  # Deduplicate by clean_id
  | unique_by(.clean_id)
  # Prepare output object
  | {
      count: length,
      users: map({
        person_id: .clean_id,
        access_time: .access_time
      })
    }
' ui-log-DD-MM-HH:MM.json > user-ids-DD-MM-HH:MM.json
```

Example output:

```json
{
  "count": 1180,
  "users": [
    {
      "person_id": "STP00038",
      "access_time": "2025-11-24T15:53:31.211494180Z"
    },
    {
      "person_id": "STP00048",
      "access_time": ""
    },
    {
      "person_id": "STP00098",
      "access_time": "2025-11-28T10:47:11.462348876Z"
    },
    {
      "person_id": "STP00114",
      "access_time": "2025-11-27T13:07:19.044068571Z"
    },
    ...
    ]
}
```

This output file can then be used to generate a heatmap using the **ui_user_heatmap.py** script.

#### Generate User Id heatmap

Generate a heatmap using the **ui_user_heatmap.py** script:

```bash
poetry run python scripts/ui_user_heatmap.py user-ids-HH-MM-HH:MM.json survey-access-heatmap-HH-MM-HH:MM.png
```

#### Generate stacked bar chart of User ID usage

Using the user ids json file you can run the following script to show the unused IDs layered with those IDs that were used.  This outputs a graph to the file _engagement_blocks.png_

```bash
poetry run python scripts/ui_all_user_ids_against_access.py user-ids-HH-MM-HH:MM.json
Saved chart → engagement_blocks.png
```
