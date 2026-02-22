#!/usr/bin/env python3

from __future__ import annotations

import argparse
import calendar
import json
import os
import re
from html import escape as html_escape
from datetime import date, timedelta
from pathlib import Path
from typing import Any


DEFAULT_TEMPLATE_PATH = Path("luxembourg_activity_templates.json")
DEFAULT_PAGES_ICS_PATH = Path("docs/luxembourg.ics")
PAGES_INDEX_TEMPLATE_PATH = Path("templates/index.template.html")
PAGES_STYLESHEET_SOURCE_PATH = Path("templates/index.css")
PAGES_SCRIPT_SOURCE_PATH = Path("templates/index.js")
PAGES_STYLESHEET_RELATIVE_PATH = Path("assets/index.css")
PAGES_SCRIPT_RELATIVE_PATH = Path("assets/index.js")
SITE_URL_ENV_VAR = "LUX_CALENDAR_SITE_URL"

WEEKDAY_INDEX = {
    "MONDAY": 0,
    "TUESDAY": 1,
    "WEDNESDAY": 2,
    "THURSDAY": 3,
    "FRIDAY": 4,
    "SATURDAY": 5,
    "SUNDAY": 6,
}

# Matches one or more emoji characters (supplementary plane + common BMP symbols)
# optionally followed by a variation selector or combining enclosing keycap.
_LEADING_EMOJI_RE = re.compile(
    r"^((?:[\u2300-\u23FF\u2600-\u27BF\U0001F000-\U0001FFFF][\uFE0F\u20E3]?)+)\s+"
)
_CAMEL_SPLIT_RE = re.compile(r"([a-z])([A-Z])")


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
    parser.add_argument(
        "--publish-pages",
        action="store_true",
        help=(
            "Write the calendar to docs/luxembourg.ics and create docs/index.html "
            "for GitHub Pages publishing."
        ),
    )
    parser.add_argument(
        "--pages-path",
        type=Path,
        default=DEFAULT_PAGES_ICS_PATH,
        help=(
            f"ICS path used with --publish-pages (default: {DEFAULT_PAGES_ICS_PATH})."
        ),
    )
    parser.add_argument(
        "--site-url",
        type=str,
        help=(
            "HTTPS URL of the published site used for subscribe links. "
            f"If omitted, the value is read from ${SITE_URL_ENV_VAR}."
        ),
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


def normalize_site_url(value: str) -> str:
    site_url = value.strip().rstrip("/")
    if not site_url.startswith(("https://", "http://")):
        raise ValueError("--site-url must start with https:// or http://")
    return site_url


def resolve_site_url(cli_value: str | None) -> str:
    if cli_value:
        return normalize_site_url(cli_value)

    env_value = os.getenv(SITE_URL_ENV_VAR)
    if env_value:
        return normalize_site_url(env_value)

    raise ValueError(
        f"Missing site URL. Provide --site-url or set ${SITE_URL_ENV_VAR} (for example in .envrc)."
    )


def to_webcal_url(http_url: str) -> str:
    if http_url.startswith("https://"):
        return f"webcal://{http_url[len('https://') :]}"
    if http_url.startswith("http://"):
        return f"webcal://{http_url[len('http://') :]}"
    raise ValueError("URL must start with https:// or http://")


def pages_root_for_path(path: Path) -> Path:
    parts = path.parts
    if "docs" in parts:
        docs_index = parts.index("docs")
        return Path(*parts[: docs_index + 1])
    return path.parent


def ordinal(value: int) -> str:
    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def month_label(value: Any) -> str:
    if isinstance(value, int) and 1 <= value <= 12:
        return calendar.month_name[value]
    return "Unknown month"


def describe_rule(rule: Any) -> str:
    if not isinstance(rule, dict):
        return "Unknown rule"

    rule_type = rule.get("type")

    if rule_type == "fixed":
        month = month_label(rule.get("month"))
        day = rule.get("day")
        if isinstance(day, int):
            return f"Fixed date: {day} {month}"
        return f"Fixed date in {month}"

    if rule_type == "easter_offset":
        offset = rule.get("days")
        if isinstance(offset, int):
            if offset == 0:
                return "Easter Sunday"
            direction = "after" if offset > 0 else "before"
            amount = abs(offset)
            day_word = "day" if amount == 1 else "days"
            return f"{amount} {day_word} {direction} Easter"
        return "Offset from Easter"

    if rule_type == "nth_weekday_of_month":
        month = month_label(rule.get("month"))
        weekday = rule.get("weekday")
        occurrence = rule.get("occurrence")
        weekday_label = weekday.title() if isinstance(weekday, str) else "Weekday"
        occurrence_label = ordinal(occurrence) if isinstance(occurrence, int) else "Nth"
        return f"{occurrence_label} {weekday_label} of {month}"

    if rule_type == "last_weekday_of_month":
        month = month_label(rule.get("month"))
        weekday = rule.get("weekday")
        weekday_label = weekday.title() if isinstance(weekday, str) else "Weekday"
        return f"Last {weekday_label} of {month}"

    if isinstance(rule_type, str) and rule_type:
        return f"Rule type: {rule_type}"
    return "Unknown rule"


def build_supported_entries_html(events: list[dict[str, Any]]) -> tuple[str, int, int]:
    cards: list[str] = []
    enabled_count = 0
    total_count = 0

    for event in events:
        if not isinstance(event, dict):
            continue

        total_count += 1
        enabled = event.get("enabled", True) is not False
        if enabled:
            enabled_count += 1

        raw_summary = str(event.get("summary", "Untitled entry"))
        emoji_match = _LEADING_EMOJI_RE.match(raw_summary)
        if emoji_match:
            icon_html = f'<span class="entry-icon" aria-hidden="true">{html_escape(emoji_match.group(1).strip())}</span>'
            title_html = html_escape(raw_summary[emoji_match.end() :])
        else:
            icon_html = ""
            title_html = html_escape(raw_summary)

        description = html_escape(
            str(event.get("description", "No description provided."))
        )
        rule_description = html_escape(describe_rule(event.get("rule")))

        location_markup = ""
        location_data = event.get("location")
        if isinstance(location_data, dict):
            loc_name = html_escape(str(location_data.get("name", "")).strip())
            loc_geo = str(location_data.get("geo", "")).strip()
            if loc_name:
                if loc_geo:
                    maps_url = f"https://maps.google.com/?q={html_escape(loc_geo)}"
                    location_markup = (
                        f'<a href="{maps_url}" target="_blank" rel="noopener noreferrer">'
                        f"{loc_name}</a>"
                    )
                else:
                    location_markup = loc_name

        categories_raw = event.get("categories")
        categories = (
            categories_raw
            if isinstance(categories_raw, list) and categories_raw
            else ["Uncategorized"]
        )
        visible_categories = [str(cat) for cat in categories]

        reference_raw = event.get("reference_url")
        if isinstance(reference_raw, str) and reference_raw.strip():
            reference_url = html_escape(reference_raw.strip())
            reference_value = f'<a href="{reference_url}" target="_blank" rel="noopener noreferrer">Reference</a>'
        else:
            reference_value = '<span class="entry-meta-na">-</span>'

        status_markup = ""
        if not enabled:
            status_markup = '<span class="entry-status">Disabled</span>'

        entry_type = categories[0].strip().lower() if categories else "other"

        location_value = (
            location_markup
            if location_markup
            else '<span class="entry-meta-na">-</span>'
        )
        tags_text = (
            html_escape(", ".join(_CAMEL_SPLIT_RE.sub(r"\1 \2", cat) for cat in visible_categories))
            if visible_categories
            else '<span class="entry-meta-na">-</span>'
        )

        footer_lines = [
            '  <div class="entry-footer">',
            '    <dl class="entry-meta">',
            f"      <dt>Rule</dt><dd>{rule_description}</dd>",
            f"      <dt>Location</dt><dd>{location_value}</dd>",
            f"      <dt>Tags</dt><dd>{tags_text}</dd>",
            f"      <dt>Source</dt><dd>{reference_value}</dd>",
            "    </dl>",
            "  </div>",
        ]

        cards.append(
            "\n".join(
                [
                    f'<article class="entry-card" data-type="{entry_type}" data-categories="{html_escape(", ".join(visible_categories))}">',
                    '  <div class="entry-header">',
                    f"    <h3>{icon_html}{title_html}</h3>",
                    f"    {status_markup}",
                    "  </div>",
                    f'  <p class="entry-description">{description}</p>',
                    *footer_lines,
                    "</article>",
                ]
            )
        )

    if not cards:
        return '<p class="empty-state">No entries configured yet.</p>', 0, 0

    return "\n".join(cards), enabled_count, total_count


def read_pages_index_template(path: Path = PAGES_INDEX_TEMPLATE_PATH) -> str:
    if not path.exists():
        raise FileNotFoundError(f"HTML template file not found: {path}")
    return path.read_text(encoding="utf-8")


def publish_pages_assets(pages_root: Path) -> list[Path]:
    assets = [
        (PAGES_STYLESHEET_SOURCE_PATH, pages_root / PAGES_STYLESHEET_RELATIVE_PATH),
        (PAGES_SCRIPT_SOURCE_PATH, pages_root / PAGES_SCRIPT_RELATIVE_PATH),
    ]

    written_paths: list[Path] = []
    for source_path, output_path in assets:
        if not source_path.exists():
            raise FileNotFoundError(f"Pages asset file not found: {source_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            source_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        written_paths.append(output_path)

    return written_paths


def render_pages_index_template(template: str, values: dict[str, str]) -> str:
    placeholders = set(re.findall(r"__([A-Z0-9_]+)__", template))
    missing = sorted(placeholders.difference(values))
    if missing:
        missing_labels = ", ".join(f"__{label}__" for label in missing)
        raise ValueError(f"Missing HTML template values: {missing_labels}")

    rendered = template
    for key in placeholders:
        rendered = rendered.replace(f"__{key}__", values[key])

    return rendered


def build_pages_index(
    ics_relative_path: str,
    start_year: int,
    end_year: int,
    events: list[dict[str, Any]],
) -> str:
    entries_markup, enabled_count, total_count = build_supported_entries_html(events)
    official_source_url = (
        "https://luxembourg.public.lu/dam-assets/publications/"
        "a-propos-des-fetes-et-traditions-au-luxembourg/"
        "a-propos-des-fetes-et-traditions-au-luxembourg-en.pdf"
    )

    return render_pages_index_template(
        read_pages_index_template(),
        {
            "OFFICIAL_SOURCE_URL": html_escape(official_source_url),
            "ICS_RELATIVE_PATH": html_escape(ics_relative_path),
            "YEAR_RANGE": f"{start_year}-{end_year}",
            "ENABLED_COUNT": str(enabled_count),
            "TOTAL_COUNT": str(total_count),
            "ENTRIES_MARKUP": entries_markup,
        },
    )


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
            reference_url_raw = event.get("reference_url")
            reference_url: str | None = None
            if reference_url_raw is not None:
                if (
                    not isinstance(reference_url_raw, str)
                    or not reference_url_raw.strip()
                ):
                    raise ValueError(f"Invalid 'reference_url' in events[{index}].")
                reference_url = reference_url_raw.strip()
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
                        "reference_url": reference_url,
                        "categories": event.get("categories"),
                    },
                )
            )

        yearly_events.sort(key=lambda item: (item[0], item[1]))

        for event_date, _, event_data in yearly_events:
            dtstart = event_date.strftime("%Y%m%d")
            dtend = (event_date + timedelta(days=1)).strftime("%Y%m%d")
            uid = f"{event_data['uid_base']}-{year}@local"

            event_lines = [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{dtstart}T000000Z",
                f"DTSTART;VALUE=DATE:{dtstart}",
                f"DTEND;VALUE=DATE:{dtend}",
                f"SUMMARY:{escape_ics_text(event_data['summary'])}",
                f"DESCRIPTION:{escape_ics_text(event_data['description'])}",
                f"CATEGORIES:{categories_to_ics(event_data['categories'])}",
            ]

            if event_data.get("reference_url"):
                event_lines.append(f"URL:{event_data['reference_url']}")

            event_lines.extend(["TRANSP:TRANSPARENT", "END:VEVENT"])

            lines.extend(event_lines)
            total_events += 1

    lines.append("END:VCALENDAR")
    return "\n".join(lines) + "\n", total_events


def main() -> None:
    args = parse_args()

    start_year = args.start_year
    end_year = args.end_year if args.end_year is not None else start_year

    if end_year < start_year:
        raise ValueError("--end-year must be >= --start-year.")
    if start_year < 1583:
        raise ValueError("Years must be >= 1583 for Gregorian Easter calculations.")

    if args.publish_pages and args.output:
        raise ValueError(
            "Use --pages-path instead of --output when --publish-pages is set."
        )

    site_url: str | None = None
    if args.publish_pages:
        site_url = resolve_site_url(args.site_url)

    if args.publish_pages:
        output_path = args.pages_path
    else:
        output_path = args.output or Path(
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(ics_content, encoding="utf-8")
    print(
        f"Generated '{output_path}' with {event_count} events for {start_year}-{end_year}."
    )

    if args.publish_pages:
        pages_root = pages_root_for_path(output_path)
        pages_root.mkdir(parents=True, exist_ok=True)
        relative_ics_path = output_path.relative_to(pages_root).as_posix()
        index_path = pages_root / "index.html"
        index_path.write_text(
            build_pages_index(
                relative_ics_path,
                start_year,
                end_year,
                template["events"],
            ),
            encoding="utf-8",
        )
        generated_assets = publish_pages_assets(pages_root)
        print(f"Generated '{index_path}' for GitHub Pages.")
        for asset_path in generated_assets:
            print(f"Generated '{asset_path}' for GitHub Pages.")

        assert site_url is not None
        ics_url = f"{site_url}/{relative_ics_path}"
        print(f"HTTPS URL: {ics_url}")
        print(f"webcal URL: {to_webcal_url(ics_url)}")


if __name__ == "__main__":
    main()
