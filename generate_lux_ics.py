#!/usr/bin/env python3

from __future__ import annotations

import argparse
import calendar
import json
import os
from html import escape as html_escape
from datetime import date, timedelta
from pathlib import Path
from typing import Any


DEFAULT_TEMPLATE_PATH = Path("luxembourg_activity_templates.json")
DEFAULT_PAGES_ICS_PATH = Path("docs/luxembourg.ics")
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
            "ICS path used with --publish-pages "
            f"(default: {DEFAULT_PAGES_ICS_PATH})."
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
        return f"webcal://{http_url[len('https://'):]}"
    if http_url.startswith("http://"):
        return f"webcal://{http_url[len('http://'):]}"
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

        summary = html_escape(str(event.get("summary", "Untitled entry")))
        description = html_escape(
            str(event.get("description", "No description provided."))
        )
        uid_base = html_escape(str(event.get("uid_base", "unknown")))
        rule_description = html_escape(describe_rule(event.get("rule")))

        categories_raw = event.get("categories")
        categories = (
            categories_raw
            if isinstance(categories_raw, list) and categories_raw
            else ["Uncategorized"]
        )
        category_markup = "".join(
            f'<span class="entry-tag">{html_escape(str(category))}</span>'
            for category in categories
        )

        reference_raw = event.get("reference_url")
        reference_markup = (
            '<span class="entry-reference unavailable">No reference URL</span>'
        )
        if isinstance(reference_raw, str) and reference_raw.strip():
            reference_url = html_escape(reference_raw.strip())
            reference_markup = (
                f'<a class="entry-reference" href="{reference_url}" '
                'target="_blank" rel="noopener noreferrer">Reference</a>'
            )

        status_markup = ""
        if not enabled:
            status_markup = '<span class="entry-status">Disabled</span>'

        cards.append(
            "\n".join(
                [
                    '<article class="entry-card">',
                    '  <div class="entry-header">',
                    f"    <h3>{summary}</h3>",
                    f"    {status_markup}",
                    "  </div>",
                    f'  <p class="entry-description">{description}</p>',
                    f'  <p class="entry-meta"><span>Rule</span>{rule_description}</p>',
                    f'  <p class="entry-meta"><span>UID</span><code>{uid_base}</code></p>',
                    f'  <div class="entry-tags">{category_markup}</div>',
                    f'  <div class="entry-source">{reference_markup}</div>',
                    "</article>",
                ]
            )
        )

    if not cards:
        return '<p class="empty-state">No entries configured yet.</p>', 0, 0

    return "\n".join(cards), enabled_count, total_count


def build_pages_index(
    ics_relative_path: str,
    start_year: int,
    end_year: int,
    events: list[dict[str, Any]],
) -> str:
    escaped_ics_path = html_escape(ics_relative_path)
    entries_markup, enabled_count, total_count = build_supported_entries_html(events)
    embedded_ics_path = json.dumps(ics_relative_path)
    official_source_url = (
        "https://luxembourg.public.lu/dam-assets/publications/"
        "a-propos-des-fetes-et-traditions-au-luxembourg/"
        "a-propos-des-fetes-et-traditions-au-luxembourg-en.pdf"
    )
    escaped_official_source_url = html_escape(official_source_url)

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Luxembourg Holidays Calendar</title>
  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\" />
  <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin />
  <link href=\"https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Work+Sans:wght@400;500;600&display=swap\" rel=\"stylesheet\" />
  <style>
    :root {{
      --ink: #1d2733;
      --muted: #4f5f72;
      --surface: rgba(255, 255, 255, 0.9);
      --line: #dce4eb;
      --teal: #0f766e;
      --orange: #c2410c;
      --bg-a: #edf8f6;
      --bg-b: #fff7ec;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: \"Work Sans\", sans-serif;
      background:
        radial-gradient(circle at 10% 8%, rgba(15, 118, 110, 0.18), transparent 45%),
        radial-gradient(circle at 88% 4%, rgba(194, 65, 12, 0.16), transparent 42%),
        linear-gradient(165deg, var(--bg-a), var(--bg-b));
    }}

    a {{
      color: var(--teal);
    }}

    .layout {{
      width: min(1120px, 92vw);
      margin: 0 auto;
      padding: 2.5rem 0 3rem;
    }}

    .hero {{
      background: var(--surface);
      border: 1px solid rgba(29, 39, 51, 0.08);
      border-radius: 24px;
      padding: clamp(1.4rem, 2vw + 1rem, 2.2rem);
      box-shadow: 0 18px 36px rgba(29, 39, 51, 0.1);
      backdrop-filter: blur(4px);
    }}

    .eyebrow {{
      margin: 0;
      color: var(--orange);
      font-size: 0.83rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-weight: 600;
    }}

    h1,
    h2,
    h3 {{
      margin: 0;
      font-family: \"Fraunces\", serif;
      line-height: 1.12;
      color: #111827;
    }}

    h1 {{
      font-size: clamp(1.9rem, 4vw, 2.9rem);
      margin-top: 0.5rem;
    }}

    .lead {{
      margin-top: 0.85rem;
      max-width: 68ch;
      color: var(--muted);
      font-size: 1.04rem;
    }}

    .actions {{
      margin-top: 1.3rem;
      display: flex;
      flex-wrap: wrap;
      gap: 0.7rem;
    }}

    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      text-decoration: none;
      font-weight: 600;
      border-radius: 999px;
      padding: 0.7rem 1rem;
      border: 1px solid transparent;
      transition: transform 150ms ease, box-shadow 150ms ease;
    }}

    .button:hover {{
      transform: translateY(-1px);
      box-shadow: 0 8px 18px rgba(17, 24, 39, 0.15);
    }}

    .button-primary {{
      background: var(--teal);
      color: #ffffff;
    }}

    .button-secondary {{
      background: #ffffff;
      color: var(--teal);
      border-color: #9fd2cb;
    }}

    .stats {{
      margin: 1.3rem 0 0;
      padding: 0;
      list-style: none;
      display: grid;
      gap: 0.7rem;
      grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
    }}

    .stats li {{
      background: rgba(255, 255, 255, 0.84);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 0.72rem 0.8rem;
    }}

    .stats strong {{
      display: block;
      font-size: 1.15rem;
      color: #0f172a;
    }}

    .stats span {{
      color: var(--muted);
      font-size: 0.88rem;
    }}

    .tip {{
      margin: 0.8rem 0 0;
      color: var(--muted);
    }}

    .entries {{
      margin-top: 1.8rem;
    }}

    .section-header h2 {{
      font-size: clamp(1.45rem, 2.6vw, 2rem);
    }}

    .section-header p {{
      margin: 0.7rem 0 0;
      color: var(--muted);
      max-width: 75ch;
    }}

    .entries-grid {{
      margin-top: 1rem;
      display: grid;
      gap: 0.95rem;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }}

    .entry-card {{
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.72rem;
      box-shadow: 0 10px 22px rgba(15, 23, 42, 0.06);
    }}

    .entry-header {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 0.7rem;
    }}

    .entry-header h3 {{
      font-size: 1.1rem;
      line-height: 1.22;
    }}

    .entry-status {{
      flex-shrink: 0;
      border: 1px solid #f4b4a3;
      color: #9a3412;
      background: #fff1ea;
      border-radius: 999px;
      padding: 0.18rem 0.55rem;
      font-size: 0.72rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    .entry-description {{
      margin: 0;
      color: var(--muted);
      font-size: 0.95rem;
      line-height: 1.45;
    }}

    .entry-meta {{
      margin: 0;
      display: flex;
      flex-direction: column;
      gap: 0.18rem;
      font-size: 0.9rem;
    }}

    .entry-meta span {{
      font-size: 0.76rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      font-weight: 600;
    }}

    .entry-meta code {{
      font-family: \"IBM Plex Mono\", \"SFMono-Regular\", monospace;
      color: #0f172a;
      word-break: break-word;
      font-size: 0.85rem;
    }}

    .entry-tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.45rem;
    }}

    .entry-tag {{
      background: #e5f3ef;
      color: #134e4a;
      border-radius: 999px;
      border: 1px solid #9fd2cb;
      font-size: 0.78rem;
      padding: 0.25rem 0.55rem;
    }}

    .entry-source {{
      margin-top: auto;
      padding-top: 0.2rem;
    }}

    .entry-reference {{
      text-underline-offset: 3px;
      font-weight: 600;
    }}

    .entry-reference.unavailable {{
      color: var(--muted);
      font-weight: 500;
    }}

    .empty-state {{
      margin-top: 1rem;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 0.9rem 1rem;
    }}

    @media (max-width: 700px) {{
      .layout {{
        width: min(1120px, 94vw);
        padding-top: 1.2rem;
      }}

      .hero {{
        border-radius: 18px;
      }}
    }}
  </style>
</head>
<body>
  <main class=\"layout\">
    <section class=\"hero\">
      <p class=\"eyebrow\">Luxembourg Calendar Feed</p>
      <h1>Luxembourg Holidays and Traditions</h1>
      <p class=\"lead\">
        A curated ICS feed with legal public holidays, recurring festivities,
        and regional fairs.
      </p>

      <p class=\"tip\">
        Official source for national holidays and traditions:
        <a href=\"{escaped_official_source_url}\" target=\"_blank\" rel=\"noopener noreferrer\">
          About... Festivals and Traditions in Luxembourg (EN, PDF)
        </a>
      </p>

      <div class=\"actions\">
        <a class=\"button button-primary\" href=\"{escaped_ics_path}\">Download ICS</a>
        <a class=\"button button-secondary\" href=\"#supported-entries\">View supported entries</a>
      </div>

      <ul class=\"stats\">
        <li><strong>{start_year}-{end_year}</strong><span>Coverage</span></li>
        <li><strong>{enabled_count}</strong><span>Enabled entries</span></li>
        <li><strong>{total_count}</strong><span>Total templates</span></li>
      </ul>

      <p class=\"tip\">iPhone tip: open the ICS link in Safari and tap \"Subscribe\".</p>
      <p class=\"tip\">Direct subscription link: <a id=\"webcal-link\" href=\"{escaped_ics_path}\">Generate webcal link</a></p>
    </section>

    <section id=\"supported-entries\" class=\"entries\">
      <div class=\"section-header\">
        <h2>All Supported Entries</h2>
        <p>
          Every template currently supported by the generator, including
          categories, recurrence rule, and reference source.
        </p>
      </div>
      <div class=\"entries-grid\">
{entries_markup}
      </div>
    </section>
  </main>

  <script>
    (function () {{
      var icsPath = {embedded_ics_path};
      var webcalLink = document.getElementById("webcal-link");
      if (!webcalLink) {{
        return;
      }}

      var absoluteUrl = new URL(icsPath, window.location.href).toString();
      var webcalUrl = absoluteUrl.replace(/^https?:\\/\\//, "webcal://");
      webcalLink.setAttribute("href", webcalUrl);
      webcalLink.textContent = webcalUrl;
    }})();
  </script>
</body>
</html>
"""


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
                    raise ValueError(
                        f"Invalid 'reference_url' in events[{index}]."
                    )
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

    if start_year < 1583 or end_year < 1583:
        raise ValueError("Years must be >= 1583 for Gregorian Easter calculations.")
    if end_year < start_year:
        raise ValueError("--end-year must be >= --start-year.")

    if args.publish_pages and args.output:
        raise ValueError("Use --pages-path instead of --output when --publish-pages is set.")

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
        print(f"Generated '{index_path}' for GitHub Pages.")

        assert site_url is not None
        ics_url = f"{site_url}/{relative_ics_path}"
        print(f"HTTPS URL: {ics_url}")
        print(f"webcal URL: {to_webcal_url(ics_url)}")


if __name__ == "__main__":
    main()
