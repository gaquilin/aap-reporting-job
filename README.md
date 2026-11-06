# AAP 2.6 Job Template Reporter

An Ansible automation designed primarily for **Ansible Automation Platform 2.6 (AAP 2.6)**, where it runs as a **Job Template**.

The automation works in these steps:

1. Launches an existing Job Template on AAP 2.6.
2. Waits for the job to finish.
3. Reads the job events from the AAP API and dynamically extracts the tasks run by the launched playbook, each with a `Success` / `Failed` outcome.
4. Emails the resulting HTML report.

The automation can also be run from the CLI, targeting an Ansible Automation Platform 2.6 instance (see [Prerequisites](#prerequisites) and [Running from CLI](#running-from-cli) sections).

## Prerequisites

### Ansible Automation Platform 2.6

The following resources must already exist on AAP 2.6:

1. Access to the Red Hat Ansible Automation Platform.
2. User credentials with permission to run the target Job Template.
3. An **Organization** with Automation Hub and its token configured, so the collections required in `collections/requirements.yml` are downloaded on Project sync.
4. A **Project** pointing to this repository.
5. The **target Job Template**, together with the resources it depends on (Organization, Inventory, Project and its credentials), already created.
6. An **SMTP server** reachable from the AAP 2.6 nodes.

### Ansible Collections

The following Ansible Collections are required. Versions are provided in `collections/requirements.yml` and are displayed below:

| Component | Version |
| --- | --- |
| `ansible.controller` | 4.8.12 |
| `community.general` | 11.4.9 |

### CLI

- Python and ansible-core (tested with Python 3.14.4 and ansible-core 2.18.12).
- Access to the AAP 2.6 API.
- User credentials with permission to run the target Job Template.
- A configured SMTP server, reachable from the machine running the playbook.

## Project Structure

```
aap-reporting-job/
├── README.md
├── ansible.cfg
├── playbook_run_jt_report.yml
├── collections/requirements.yml
├── filter_plugins/job_report.py  # builds the per-task report
├── roles/job_report/
│   ├── defaults/main.yml         # default variables
│   ├── meta/argument_specs.yml
│   ├── tasks/
│   │   ├── main.yml
│   │   ├── launch.yml            # launches the target job and waits for it to finish
│   │   ├── wait_events.yml
│   │   ├── collect.yml           # collects the job results
│   │   └── notify.yml            # sends the report by email
│   └── templates/report.html.j2
```

## Automation Execution

### Running from AAP 2.6

1. Go to **Automation Execution → Templates** and select **Create template → Create job template**.
2. Provide the required fields:
   - **Name**: e.g. `Job Report - My Target Job Template`.
   - **Inventory** (the playbook runs on `localhost`).
   - **Project**: the Project pointing to this repository.
   - **Playbook**: `playbook_run_jt_report.yml`.
3. In **Extra variables**, provide the required variables:

   ```yaml
   job_report_target_template: "My Target Job Template"
   job_report_smtp_host: smtp.example.com
   job_report_smtp_port: 25
   job_report_mail_from: aap-noreply@example.com
   job_report_mail_to:
     - team@example.com
   ```
4. Save the Job Template.
5. Launch the Job Template: check that the target job runs and the email is received.

### Running from CLI

1. Provide a valid token in the `ansible.cfg` file to download Collections from the Red Hat Public Automation Hub.
2. Install the Collections:

   ```bash
   ansible-galaxy collection install -r collections/requirements.yml -p collections/
   ```
3. Export the AAP connection variables (Username and Password):

   ```bash
   export CONTROLLER_HOST=https://aap.example.com
   export CONTROLLER_USERNAME=<user>
   export CONTROLLER_PASSWORD=<password>
   ```
4. Create a variable file (e.g. `vars.yml`), providing the required variables:

   ```yaml
   job_report_target_template: "My Target Job Template"
   job_report_smtp_host: smtp.example.com
   job_report_smtp_port: 25
   job_report_mail_from: aap-noreply@example.com
   job_report_mail_to:
     - team@example.com
   ```
5. Run the playbook:

   ```bash
   ansible-playbook playbook_run_jt_report.yml -e @vars.yml
   ```

## Automation Overview

The following section gives an overview of the Ansible playbook and role files developed for this automation and their purpose, together with the variables that can be used to configure it.

### Playbook and roles overview

| File | Details |
| --- | --- |
| `playbook_run_jt_report.yml` | Entry point: runs on `localhost` and calls the `job_report` role. |
| `roles/job_report/tasks/main.yml` | Validates the input values and runs the steps in order; at the end, fails if the target job did not succeed. |
| `roles/job_report/tasks/launch.yml` | Launches the target Job Template and waits for the job to finish. |
| `roles/job_report/tasks/wait_events.yml` | Waits until AAP has stored all the events of the job. |
| `roles/job_report/tasks/collect.yml` | Reads the job events and host summaries and builds the per-task report. |
| `roles/job_report/tasks/notify.yml` | Sends the HTML report by email. |
| `roles/job_report/defaults/main.yml` | Default values of all variables. |
| `roles/job_report/meta/argument_specs.yml` | Checks that the required variables are set and have the right type. |
| `roles/job_report/templates/report.html.j2` | HTML template of the email. |
| `filter_plugins/job_report.py` | Python filter that turns the job events into the list of executed tasks, each with its outcome. |

## Variables

### `roles/job_report/defaults/main.yml`

| Variable | Default | Required | Details |
| --- | --- | --- | --- |
| `job_report_target_template` | `""` | Yes | Name or ID of the Job Template to run |
| `job_report_target_organization` | `""` | No | Organization of the target Job Template, when several have the same name |
| `job_report_target_extra_vars` | `{}` | No | Extra variables passed to the target job (needs *Prompt on launch* on the target) |
| `job_report_target_limit` | `""` | No | Host limit passed to the target job (needs *Prompt on launch*) |
| `job_report_target_tags` | `""` | No | Tags passed to the target job (needs *Prompt on launch*) |
| `job_report_timeout` | `7200` | No | Maximum wait for the target job, in seconds |
| `job_report_poll_interval` | `15` | No | Seconds between two checks of the target job status |
| `job_report_event_wait_retries` | `24` | No | After the target job ends, how many times to check that AAP has finished storing its events |
| `job_report_event_wait_delay` | `5` | No | Seconds to wait between two checks of the event storage |
| `job_report_max_events` | `100000` | No | Maximum number of job events read from the API |
| `job_report_include_gather_facts` | `true` | No | Show or hide the "Gathering Facts" task in the report |
| `job_report_ignored_as_failed` | `false` | No | Report failures with `ignore_errors` as Failed |
| `job_report_max_msg_len` | `300` | No | Maximum length of each error message in the report |
| `job_report_include_error_messages` | `true` | No | Show the error messages in the report |
| `job_report_controller_url` | `CONTROLLER_HOST` | No | Base URL of AAP, used for the link in the email |
| `job_report_job_url_path` | `/execution/jobs/playbook/{id}/output` | No | Path of the job page in the AAP UI, used for the link in the email |
| `job_report_smtp_host` | `""` | Yes | SMTP server host |
| `job_report_smtp_port` | `25` | No | SMTP server port |
| `job_report_mail_from` | `""` | Yes | Sender address |
| `job_report_mail_to` | `[]` | Yes | List of recipient addresses |
| `job_report_mail_subject` | `""` | No | Email subject; empty = automatic subject `[AAP Job Report] SUCCESS/FAIL - <AAP hostname> - <JT>` |
| `job_report_fail_on_target_failure` | `true` | No | Fail the report job, after sending the email, if the target job did not succeed |

### Playbook variables

`playbook_run_jt_report.yml` receives variables as extra vars and passes them to the role. The following are the ones that must always be provided:

| Variable | Example | Details |
| --- | --- | --- |
| `job_report_target_template` | `"My Target Job Template"` | Job Template to run |
| `job_report_smtp_host` | `smtp.example.com` | SMTP server host |
| `job_report_smtp_port` | `25` | SMTP server port (optional, default 25) |
| `job_report_mail_from` | `aap-noreply@example.com` | Sender address |
| `job_report_mail_to` | `[team@example.com]` | Recipients |
