#!/usr/bin/env python3

from __future__ import annotations

import argparse
import calendar
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any


DEFAULT_TEMPLATE_PATH = Path("luxembourg_activity_templates.json")

WEEKDAY_INDEX = {
    "MONDAY": 0,
    "TUESDAY": 1,
    "WEDNESDAY": 2,
    "THURSDAY": 3,
    "FRIDAY": 4,
    "SATURDAY": 5,
    "SUNDAY": 6,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate an ICS calendar for Luxembourg holidays/festivities/fairs "
            "from editable activity templates."
        )
    )
    parser.add_argument(
        "--start-year",
        type=int,
        required=True,
        help="First year to generate (inclusive).",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        help="Last year to generate (inclusive). Defaults to --start-year.",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE_PATH,
        help=(
            "Path to the editable template JSON file "
            f"(default: {DEFAULT_TEMPLATE_PATH})."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output ICS file path.",
    )
    parser.add_argument(
        "--calname",
        type=str,
        help="Override calendar name from template.",
    )
    parser.add_argument(
        "--caldesc",
        type=str,
        help="Override calendar description from template.",
    )
    parser.add_argument(
        "--prodid",
        type=str,
        help="Override calendar PRODID from template.",
    )
    return parser.parse_args()


def gregorian_easter(year: int) -> date:
    # https://en.wikipedia.org/wiki/Date_of_Easter#Anonymous_Gregorian_algorithm
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def escape_ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def categories_to_ics(categories: Any) -> str:
    if isinstance(categories, str):
        return escape_ics_text(categories)
    if not isinstance(categories, list) or not categories:
        raise ValueError("Each event must define non-empty categories.")
    return "\\;".join(escape_ics_text(str(category)) for category in categories)


def required_str(obj: dict[str, Any], key: str, context: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing or invalid '{key}' in {context}.")
    return value


def replace_range_tokens(value: str, start_year: int, end_year: int) -> str:
    return value.replace("{start_year}", str(start_year)).replace(
        "{end_year}", str(end_year)
    )


def to_int(value: Any, field_name: str, rule_type: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Rule '{rule_type}' requires integer '{field_name}'.")
    return value


def resolve_rule(rule: dict[str, Any], year: int, easter: date) -> date:
    rule_type = required_str(rule, "type", "rule")

    if rule_type == "fixed":
        month = to_int(rule.get("month"), "month", rule_type)
        day = to_int(rule.get("day"), "day", rule_type)
        return date(year, month, day)

    if rule_type == "easter_offset":
        offset = to_int(rule.get("days"), "days", rule_type)
        return easter + timedelta(days=offset)

    if rule_type == "nth_weekday_of_month":
        month = to_int(rule.get("month"), "month", rule_type)
        occurrence = to_int(rule.get("occurrence"), "occurrence", rule_type)
        weekday_name = required_str(rule, "weekday", "rule").upper()
        weekday = WEEKDAY_INDEX.get(weekday_name)
        if weekday is None:
            raise ValueError(
                f"Unsupported weekday '{weekday_name}' in '{rule_type}' rule."
            )
        if occurrence < 1:
            raise ValueError("'occurrence' must be >= 1 for nth_weekday_of_month.")

        first_day = date(year, month, 1)
        first_delta = (weekday - first_day.weekday()) % 7
        day = 1 + first_delta + (occurrence - 1) * 7
        _, days_in_month = calendar.monthrange(year, month)
        if day > days_in_month:
            raise ValueError(
                f"Invalid nth_weekday_of_month rule for year {year}: day {day} does not exist."
            )
        return date(year, month, day)

    if rule_type == "last_weekday_of_month":
        month = to_int(rule.get("month"), "month", rule_type)
        weekday_name = required_str(rule, "weekday", "rule").upper()
        weekday = WEEKDAY_INDEX.get(weekday_name)
        if weekday is None:
            raise ValueError(
                f"Unsupported weekday '{weekday_name}' in '{rule_type}' rule."
            )

        _, days_in_month = calendar.monthrange(year, month)
        last_day = date(year, month, days_in_month)
        delta = (last_day.weekday() - weekday) % 7
        return last_day - timedelta(days=delta)

    raise ValueError(f"Unsupported rule type: '{rule_type}'.")


def load_template(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Template file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in template file '{path}': {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Template root must be a JSON object.")

    calendar_meta = data.get("calendar")
    if not isinstance(calendar_meta, dict):
        raise ValueError("Template must include a 'calendar' object.")

    events = data.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("Template must include a non-empty 'events' list.")

    return data


def build_ics(
    template: dict[str, Any],
    start_year: int,
    end_year: int,
    calname_override: str | None,
    caldesc_override: str | None,
    prodid_override: str | None,
) -> tuple[str, int]:
    calendar_meta = template["calendar"]
    events: list[dict[str, Any]] = template["events"]

    calname = calname_override or required_str(calendar_meta, "calname", "calendar")
    caldesc = caldesc_override or required_str(calendar_meta, "caldesc", "calendar")
    prodid = prodid_override or required_str(calendar_meta, "prodid", "calendar")
    published_ttl = required_str(calendar_meta, "published_ttl", "calendar")

    calname = replace_range_tokens(calname, start_year, end_year)
    caldesc = replace_range_tokens(caldesc, start_year, end_year)
    prodid = replace_range_tokens(prodid, start_year, end_year)

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{prodid}",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{escape_ics_text(calname)}",
        f"X-WR-CALDESC:{escape_ics_text(caldesc)}",
        f"X-PUBLISHED-TTL:{published_ttl}",
    ]

    total_events = 0
    for year in range(start_year, end_year + 1):
        easter = gregorian_easter(year)
        yearly_events: list[tuple[date, int, dict[str, Any]]] = []

        for index, event in enumerate(events):
            if not isinstance(event, dict):
                raise ValueError("Each item in 'events' must be a JSON object.")
            if event.get("enabled", True) is False:
                continue

            uid_base = required_str(event, "uid_base", f"events[{index}]")
            summary = required_str(event, "summary", f"events[{index}]")
            description = required_str(event, "description", f"events[{index}]")
            rule = event.get("rule")
            if not isinstance(rule, dict):
                raise ValueError(f"Missing or invalid 'rule' in events[{index}].")

            summary = replace_range_tokens(summary, start_year, end_year)
            description = replace_range_tokens(description, start_year, end_year)

            event_date = resolve_rule(rule, year, easter)
            yearly_events.append(
                (
                    event_date,
                    index,
                    {
                        "uid_base": uid_base,
                        "summary": summary,
                        "description": description,
                        "categories": event.get("categories"),
                    },
                )
            )

        yearly_events.sort(key=lambda item: (item[0], item[1]))

        for event_date, _, event_data in yearly_events:
            dtstart = event_date.strftime("%Y%m%d")
            dtend = (event_date + timedelta(days=1)).strftime("%Y%m%d")
            uid = f"{event_data['uid_base']}-{year}@local"

            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    f"DTSTAMP:{dtstart}T000000Z",
                    f"DTSTART;VALUE=DATE:{dtstart}",
                    f"DTEND;VALUE=DATE:{dtend}",
                    f"SUMMARY:{escape_ics_text(event_data['summary'])}",
                    f"DESCRIPTION:{escape_ics_text(event_data['description'])}",
                    f"CATEGORIES:{categories_to_ics(event_data['categories'])}",
                    "TRANSP:TRANSPARENT",
                    "END:VEVENT",
                ]
            )
            total_events += 1

    lines.append("END:VCALENDAR")
    return "\n".join(lines) + "\n", total_events


def main() -> None:
    args = parse_args()

    start_year = args.start_year
    end_year = args.end_year if args.end_year is not None else start_year

    if start_year < 1583 or end_year < 1583:
        raise ValueError("Years must be >= 1583 for Gregorian Easter calculations.")
    if end_year < start_year:
        raise ValueError("--end-year must be >= --start-year.")

    output_path: Path = args.output or Path(
        f"luxembourg_holidays_festivities_fairs_{start_year}_{end_year}.ics"
    )

    template = load_template(args.template)
    ics_content, event_count = build_ics(
        template,
        start_year,
        end_year,
        args.calname,
        args.caldesc,
        args.prodid,
    )

    output_path.write_text(ics_content, encoding="utf-8")
    print(
        f"Generated '{output_path}' with {event_count} events for {start_year}-{end_year}."
    )


if __name__ == "__main__":
    main()
