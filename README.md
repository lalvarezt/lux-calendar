# Luxembourg Holidays ICS Generator

This repository includes:

- `luxembourg_activity_templates.json`: editable activity templates (one entry per holiday/festivity/fair)
- `generate_lux_ics.py`: script that generates an `.ics` file from those templates

## Generate an ICS file

```bash
python generate_lux_ics.py --start-year 2026 --end-year 2028
```

This creates:

- `luxembourg_holidays_festivities_fairs_2026_2028.ics`

You can also set the output name:

```bash
python generate_lux_ics.py --start-year 2026 --end-year 2028 --output custom.ics
```

## Update holiday templates

Edit `luxembourg_activity_templates.json` and update any entry fields, for example:

- `summary`
- `description`
- `categories`
- `rule`

Each event is an individual JSON object in `events`, so titles/descriptions can be changed independently.

Optional: set `"enabled": false` on an entry to exclude it from output.

## Rule types

- `fixed`: fixed day each year (`month`, `day`)
- `easter_offset`: days relative to Easter Sunday (`days`)
- `nth_weekday_of_month`: e.g. first Monday of September (`month`, `weekday`, `occurrence`)
- `last_weekday_of_month`: e.g. last Friday of August (`month`, `weekday`)

## Calendar text tokens

`calname` and `caldesc` support:

- `{start_year}`
- `{end_year}`

These are replaced when generating the file.
