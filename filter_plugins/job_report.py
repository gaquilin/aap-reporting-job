# -*- coding: utf-8 -*-
"""Filters that build a per-task report from AAP job events.

The report does not know the target playbook's tasks in advance: it derives
them from the job events (playbook_on_task_start / runner_on_*), so any change
to the target playbook is reflected in the report automatically.
"""

START_EVENTS = {
    "playbook_on_task_start": "task",
    "playbook_on_handler_task_start": "handler",
}

RESULT_EVENTS = {
    "runner_on_ok": "ok",
    "runner_on_async_ok": "ok",
    "runner_on_failed": "failed",
    "runner_on_async_failed": "failed",
    "runner_on_skipped": "skipped",
    "runner_on_unreachable": "unreachable",
}

EVENT_TYPES = sorted(list(START_EVENTS) + list(RESULT_EVENTS))

GATHER_ACTIONS = {
    "gather_facts",
    "setup",
    "ansible.builtin.gather_facts",
    "ansible.builtin.setup",
}


def _clean(text, max_len):
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    text = " ".join(text.split())
    if max_len and len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def _error_message(res, max_len):
    """Extract a readable error message from an event's 'res'."""
    if not isinstance(res, dict):
        return ""
    msg = res.get("msg") or res.get("reason") or res.get("stderr") or ""
    if not msg and isinstance(res.get("results"), list):
        for item in res["results"]:
            if isinstance(item, dict) and (item.get("failed") or item.get("unreachable")):
                msg = item.get("msg") or item.get("stderr") or ""
                if msg:
                    break
    return _clean(msg, max_len)


def _task_key(event, event_data):
    if event_data.get("task_uuid"):
        return event_data["task_uuid"]
    if event.get("event") in START_EVENTS and event.get("uuid"):
        return event["uuid"]
    return "|".join(
        [event.get("play") or "", event.get("role") or "", event.get("task") or ""]
    )


def _new_task(event, event_data):
    task_name = event.get("task") or event_data.get("task") or event_data.get("name") or "(unnamed)"
    role = event.get("role") or event_data.get("role") or ""
    return {
        "play": event.get("play") or event_data.get("play") or "",
        "role": role,
        "name": task_name,
        "display_name": "%s : %s" % (role, task_name) if role else task_name,
        "kind": "task",
        "first_counter": event.get("counter") or 0,
        "is_gather_facts": False,
        "hosts": {
            "ok": 0,
            "changed": 0,
            "failed": 0,
            "ignored": 0,
            "skipped": 0,
            "unreachable": 0,
        },
        "failed_hosts": [],
        "unreachable_hosts": [],
        "messages": [],
    }


def task_report(events, ignored_as_failed=False, include_gather_facts=True, max_msg_len=300):
    """Aggregate job events into an ordered list of tasks with an outcome.

    Outcome per task:
      * Failed  -> at least one host failed (not ignored) or unreachable;
                   with ignored_as_failed=True also failures with ignore_errors.
      * Success -> every other case (ok, changed, skipped).
    """
    tasks = {}
    order = []

    for event in sorted(events or [], key=lambda e: e.get("counter") or 0):
        if not isinstance(event, dict):
            continue
        etype = event.get("event")
        if etype not in START_EVENTS and etype not in RESULT_EVENTS:
            continue
        event_data = event.get("event_data") or {}
        key = _task_key(event, event_data)

        task = tasks.get(key)
        if task is None:
            task = _new_task(event, event_data)
            tasks[key] = task
            order.append(key)

        action = event_data.get("task_action") or ""
        if task["name"] == "Gathering Facts" or action in GATHER_ACTIONS:
            task["is_gather_facts"] = True

        if etype in START_EVENTS:
            task["kind"] = START_EVENTS[etype]
            continue

        kind = RESULT_EVENTS[etype]
        host = event.get("host_name") or event_data.get("host") or "?"
        res = event_data.get("res")

        if kind == "ok":
            task["hosts"]["ok"] += 1
            if event.get("changed") or (isinstance(res, dict) and res.get("changed")):
                task["hosts"]["changed"] += 1
        elif kind == "skipped":
            task["hosts"]["skipped"] += 1
        elif kind == "unreachable":
            task["hosts"]["unreachable"] += 1
            task["unreachable_hosts"].append(host)
            msg = _error_message(res, max_msg_len)
            task["messages"].append("%s: %s" % (host, msg or "unreachable"))
        elif kind == "failed":
            msg = _error_message(res, max_msg_len)
            if event_data.get("ignore_errors"):
                task["hosts"]["ignored"] += 1
                if ignored_as_failed:
                    task["failed_hosts"].append(host)
                task["messages"].append("%s (ignored): %s" % (host, msg or "failed"))
            else:
                task["hosts"]["failed"] += 1
                task["failed_hosts"].append(host)
                task["messages"].append("%s: %s" % (host, msg or "failed"))

    result = []
    for key in order:
        task = tasks[key]
        if task["is_gather_facts"] and not include_gather_facts:
            continue
        failed = task["hosts"]["failed"] or task["hosts"]["unreachable"]
        if ignored_as_failed and task["hosts"]["ignored"]:
            failed = True
        task["outcome"] = "Failed" if failed else "Success"
        task["index"] = len(result) + 1
        result.append(task)

    failed_tasks = [t for t in result if t["outcome"] == "Failed"]
    return {
        "tasks": result,
        "summary": {
            "total": len(result),
            "success": len(result) - len(failed_tasks),
            "failed": len(failed_tasks),
            "failed_tasks": [t["display_name"] for t in failed_tasks],
        },
    }


def job_event_types(_unused=None):
    """Event types to pass to event__in in the API."""
    return EVENT_TYPES


def as_list(value):
    """Normalize the controller_api lookup result into a list."""
    if value in (None, ""):
        return []
    if isinstance(value, dict):
        return [value]
    return list(value)


class FilterModule(object):
    def filters(self):
        return {
            "job_report_tasks": task_report,
            "job_report_event_types": job_event_types,
            "job_report_as_list": as_list,
        }
