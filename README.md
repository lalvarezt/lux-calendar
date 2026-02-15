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

## Publish with GitHub Pages

Generate a publishable Pages bundle (ICS + landing page):

```bash
python generate_lux_ics.py --start-year 2000 --end-year 2100 --publish-pages
```

This creates:

- `docs/luxembourg.ics`
- `docs/index.html`

If you already know your Pages URL, print ready-to-use subscribe links:

```bash
python generate_lux_ics.py --start-year 2000 --end-year 2100 --publish-pages --site-url https://<username>.github.io/<repository>
```

### GitHub configuration (one-time)

1. Push your repository changes to GitHub.
2. Open **Settings** → **Pages**.
3. Under **Build and deployment**, choose **Deploy from a branch**.
4. Select branch `main` (or `master`) and folder `/docs`, then save.
5. Wait for Pages to publish, then use:
   - `https://<username>.github.io/<repository>/luxembourg.ics`
   - `webcal://<username>.github.io/<repository>/luxembourg.ics` (recommended for iPhone subscription)

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
