# Card Maker UI (Magic: The Gathering)

A simple web form for non-engineers. Paste a Magic: The Gathering deck URL, watch the
card art download live, then generate and download a print-ready PDF — no terminal
commands required.

It wraps the existing [`plugins/mtg/fetch.py`](../plugins/mtg/README.md) (using the
`url` deck format) and [`create_pdf.py`](../README.md#create_pdfpy) logic.

## Quick start (recommended)

You only need **Python 3** installed. The launcher sets everything else up for you —
it creates the virtual environment, installs dependencies, starts the server, and opens
your browser automatically.

- **macOS:** double-click **`ui/start.command`** (or run `python3 ui/run.py`).
- **Windows:** double-click **`ui\start.bat`** (or run `python ui\run.py`).
- **Linux / any OS:** run `python3 ui/run.py`.

The first launch takes a few minutes while dependencies install. Later launches start in
seconds. Leave the terminal window open while you use the app; close it (or press Ctrl+C)
to stop the server.

> Don't have Python yet? Install it from <https://www.python.org/downloads/>. On Windows,
> check **"Add Python to PATH"** during installation.

## Manual setup (alternative)

If you'd rather manage the environment yourself, from the **repository root** with your
virtual environment activated (see the [root README](../README.md#basic-usage)):

```sh
pip install -r requirements.txt        # core dependencies
pip install -r ui/requirements.txt     # adds Flask for the UI
python ui/app.py                        # then open http://127.0.0.1:5000
```

## How to use

1. **Fetch card art** — paste a deck URL (Moxfield, Archidekt, Deckstats, MTG Goldfish,
   Scryfall, Tapped Out, TCGPlayer, Aetherhub, MTGJSON). Optionally open *Advanced fetch
   options* to prefer sets, languages, showcase/extra art, etc. Click **Fetch cards** and
   the art appears in the scrollable grid as it downloads. **Click any card to view it
   larger** (double-sided cards show both faces); click the backdrop, the ✕, or press
   `Esc` to close.
2. **Create PDF** — pick a card size, paper size, and registration marks (plus any
   advanced layout options), then click **Generate & download PDF**.

Your fetch and PDF option selections are **remembered in your browser** (via local
storage) and restored automatically next time, so you don't have to re-enter your
preferred settings. The deck URL itself is not saved.

## Notes

- Images are written to and read from the repo's `game/front/` and `game/double_sided/`
  directories, exactly like the command-line tools. Each fetch clears those directories
  **first**, so only the most recent deck is kept — and a previous deck's art can never
  bleed into a new one.
- The fetched art stays on disk after you generate a PDF, so you can change layout options
  (card size, paper size, crop, etc.) and **generate again without re-fetching**. Fetching
  a new deck wipes the previous one.
- The generated PDF is saved to `game/output/game.pdf` and downloaded by the browser.
- This is a local, single-user development server. Don't expose it to the public internet.
