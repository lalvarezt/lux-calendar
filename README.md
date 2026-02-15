# Luxembourg Holidays Calendar

Live links:

- Site: `https://lalvarezt.github.io/lux-calendar/`
- ICS file: `https://lalvarezt.github.io/lux-calendar/luxembourg.ics`
- iPhone subscription: `webcal://lalvarezt.github.io/lux-calendar/luxembourg.ics`

Repository files:

- `luxembourg_activity_templates.json`: editable holiday/festivity templates
- `generate_lux_ics.py`: ICS generator
- `docs/luxembourg.ics`: published calendar file (GitHub Pages)
- `docs/index.html`: simple landing page for downloads/subscription

## Generate and publish (GitHub Pages)

Set your site URL once (local environment):

```bash
cp .envrc.example .envrc
direnv allow
```

Without `direnv`, export it manually in your shell:

```bash
export LUX_CALENDAR_SITE_URL="https://your-username.github.io/your-repository"
```

Run:

```bash
python generate_lux_ics.py --start-year 2000 --end-year 2100 --publish-pages
```

This updates:

- `docs/luxembourg.ics`
- `docs/index.html`

The script reads `LUX_CALENDAR_SITE_URL` from `.envrc` for the printed HTTPS/webcal links.
You can still override it explicitly with `--site-url`.

## Generate a local custom ICS (optional)

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
