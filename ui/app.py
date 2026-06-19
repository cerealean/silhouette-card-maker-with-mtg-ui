import json
import os
import queue
import sys
import threading
from itertools import count

# Force matplotlib's headless backend before any repo module imports pyplot
# (page_manager.py does, transitively, via utilities). The default macOS backend
# crashes the process when used from Flask's worker threads.
os.environ.setdefault('MPLBACKEND', 'Agg')

from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_file,
    send_from_directory,
)

# Allow importing the repo's modules (plugins, utilities) when run from anywhere.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from plugins.mtg.common import ScryfallLanguage
from plugins.mtg.deck_formats import DeckFormat, parse_deck
from plugins.mtg.scryfall import get_handle_card as scryfall_get_handle_card
from utilities import (
    Registration,
    FitMode,
    ensure_directory,
    generate_pdf,
    get_all_card_size_names,
    get_all_paper_size_names,
    get_all_specialty_layout_names,
    load_layout_config,
)

FRONT_DIR = os.path.join(REPO_ROOT, 'game', 'front')
BACK_DIR = os.path.join(REPO_ROOT, 'game', 'back')
DOUBLE_SIDED_DIR = os.path.join(REPO_ROOT, 'game', 'double_sided')
OUTPUT_DIR = os.path.join(REPO_ROOT, 'game', 'output')
OUTPUT_PDF = os.path.join(OUTPUT_DIR, 'game.pdf')

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}

app = Flask(__name__)

layout_config = load_layout_config()

_jobs: dict[str, "queue.Queue"] = {}
_job_ids = count(1)
_jobs_lock = threading.Lock()


def is_image(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS


def list_images(directory: str) -> set[str]:
    if not os.path.isdir(directory):
        return set()
    return {f for f in os.listdir(directory) if is_image(f)}


def clear_images(directory: str) -> None:
    for filename in list_images(directory):
        try:
            os.remove(os.path.join(directory, filename))
        except OSError:
            pass


def as_list(value) -> list[str]:
    """Normalize a form value (string or list) into a clean list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        value = value.replace(',', ' ').split()
    return [item.strip() for item in value if str(item).strip()]


def run_fetch(deck_url: str, options: dict, event_queue: "queue.Queue") -> None:
    """Fetch all card art for a deck URL, emitting one event per processed card."""

    def emit(event: str, payload: dict) -> None:
        event_queue.put((event, payload))

    try:
        ensure_directory(FRONT_DIR)
        ensure_directory(DOUBLE_SIDED_DIR)
        # Clear any art from a previous deck before fetching, so the two never mix.
        clear_images(FRONT_DIR)
        clear_images(DOUBLE_SIDED_DIR)

        emit('log', {'message': f'Parsing deck from {deck_url} ...'})

        prefer_langs = [ScryfallLanguage(lang) for lang in options['prefer_lang']] or None

        real_handle_card = scryfall_get_handle_card(
            options['ignore_set_and_collector_number'],
            options['prefer_older_sets'],
            options['prefer_set'],
            options['ignore_set'],
            options['prefer_showcase'],
            options['prefer_extra_art'],
            options['prefer_ub'],
            options['ignore_ub'],
            prefer_langs,
            options['tokens'],
            FRONT_DIR,
            DOUBLE_SIDED_DIR,
        )

        processed = 0

        def handle_card(index, name, card_set=None, collector_number=None, quantity=1):
            nonlocal processed
            before_front = list_images(FRONT_DIR)
            before_back = list_images(DOUBLE_SIDED_DIR)

            real_handle_card(index, name, card_set, collector_number, quantity)

            new_front = sorted(list_images(FRONT_DIR) - before_front)
            new_back = sorted(list_images(DOUBLE_SIDED_DIR) - before_back)

            processed += 1
            emit('card', {
                'index': index,
                'name': name,
                'quantity': quantity,
                'front': new_front[0] if new_front else None,
                'back': new_back[0] if new_back else None,
            })

        parse_deck(deck_url, DeckFormat.URL, handle_card, FRONT_DIR, DOUBLE_SIDED_DIR)

        emit('done', {'count': processed, 'images': len(list_images(FRONT_DIR))})
    except Exception as exc:  # noqa: BLE001 - surface any failure to the client
        emit('error', {'message': str(exc)})
    finally:
        event_queue.put(None)  # sentinel: stream complete


@app.route('/')
def index():
    return render_template(
        'index.html',
        card_sizes=get_all_card_size_names(layout_config),
        paper_sizes=get_all_paper_size_names(layout_config),
        specialty_layouts=get_all_specialty_layout_names(layout_config),
        registrations=[r.value for r in Registration],
        fit_modes=[f.value for f in FitMode],
        languages=[(lang.value, lang.name.replace('_', ' ').title()) for lang in ScryfallLanguage],
    )


@app.route('/api/fetch', methods=['POST'])
def start_fetch():
    data = request.get_json(force=True)
    deck_url = (data.get('url') or '').strip()
    if not deck_url:
        return jsonify({'error': 'A deck URL is required.'}), 400

    options = {
        'ignore_set_and_collector_number': bool(data.get('ignore_set_and_collector_number')),
        'prefer_older_sets': bool(data.get('prefer_older_sets')),
        'prefer_set': as_list(data.get('prefer_set')),
        'ignore_set': as_list(data.get('ignore_set')),
        'prefer_showcase': bool(data.get('prefer_showcase')),
        'prefer_extra_art': bool(data.get('prefer_extra_art')),
        'prefer_ub': bool(data.get('prefer_ub')),
        'ignore_ub': bool(data.get('ignore_ub')),
        'prefer_lang': as_list(data.get('prefer_lang')),
        'tokens': bool(data.get('tokens')),
    }

    event_queue: "queue.Queue" = queue.Queue()
    with _jobs_lock:
        job_id = str(next(_job_ids))
        _jobs[job_id] = event_queue

    thread = threading.Thread(target=run_fetch, args=(deck_url, options, event_queue), daemon=True)
    thread.start()

    return jsonify({'job_id': job_id})


@app.route('/api/fetch/<job_id>/events')
def fetch_events(job_id: str):
    event_queue = _jobs.get(job_id)
    if event_queue is None:
        return jsonify({'error': 'Unknown job.'}), 404

    def stream():
        try:
            while True:
                item = event_queue.get()
                if item is None:
                    break
                event, payload = item
                yield f'event: {event}\ndata: {json.dumps(payload)}\n\n'
        finally:
            with _jobs_lock:
                _jobs.pop(job_id, None)

    return Response(stream(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
    })


@app.route('/api/image/front/<path:filename>')
def image_front(filename: str):
    return send_from_directory(FRONT_DIR, filename)


@app.route('/api/image/back/<path:filename>')
def image_back(filename: str):
    return send_from_directory(DOUBLE_SIDED_DIR, filename)


@app.route('/api/generate-pdf', methods=['POST'])
def generate_pdf_route():
    data = request.get_json(force=True)

    if not list_images(FRONT_DIR):
        return jsonify({'error': 'No card images found. Fetch a deck first.'}), 400

    def to_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    skip_indices = [to_int(v, None) for v in as_list(data.get('skip'))]
    skip_indices = [v for v in skip_indices if v is not None]

    ensure_directory(OUTPUT_DIR)

    try:
        generate_pdf(
            FRONT_DIR,
            BACK_DIR,
            DOUBLE_SIDED_DIR,
            OUTPUT_PDF,
            False,  # output_images
            data.get('card_size') or 'standard',
            data.get('paper_size') or 'letter',
            data.get('registration') or Registration.THREE.value,
            bool(data.get('only_fronts')),
            data.get('fit') or FitMode.STRETCH.value,
            (data.get('crop') or '').strip() or None,
            (data.get('crop_backs') or '').strip() or None,
            to_int(data.get('extend_corners'), 0),
            to_int(data.get('ppi'), 300),
            to_int(data.get('quality'), 100),
            skip_indices,
            bool(data.get('load_offset')),
            (data.get('label') or '').strip() or None,
            show_outline=bool(data.get('show_outline')),
            specialty=(data.get('specialty') or None),
            borderless=bool(data.get('borderless')),
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({'error': str(exc)}), 500

    # Leave the fetched art in place so the user can tweak options and regenerate
    # without re-fetching. The next fetch clears these directories first.
    return jsonify({'download_url': '/api/download'})


@app.route('/api/download')
def download_pdf():
    if not os.path.isfile(OUTPUT_PDF):
        return jsonify({'error': 'No PDF has been generated yet.'}), 404
    return send_file(OUTPUT_PDF, as_attachment=True, download_name='game.pdf')


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, threaded=True, debug=True)
