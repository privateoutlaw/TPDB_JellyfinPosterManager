"""Optional real-browser smoke test with fake services and disposable state.

python -m tests.browser_smoke --browser /path/to/Chromium --driver /path/to/chromedriver
CDN-hosted Bootstrap/Font Awesome assets need network access; media services are mocked.
"""
import argparse
import io
import os
import tempfile
import threading
from contextlib import ExitStack
from unittest.mock import patch

from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from werkzeug.serving import make_server

from app import create_app
from jobs import JobQueue
from poster_service import PosterService
from state_store import StateStore
from tests.test_workflows import ITEM, SELECTION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', required=True)
    parser.add_argument('--driver', required=True)
    parser.add_argument('--screenshot')
    args = parser.parse_args()
    movie = dict(ITEM, id='movie', title='Another Example', type='Movie')
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        store = StateStore(os.path.join(directory, 'test.sqlite3'))
        service = PosterService(store)
        queue = JobQueue(store, service, delay=0, start_worker=False)
        app = create_app({'TESTING': True, 'CACHE_DIR': directory}, store=store, job_queue=queue)
        store.set_selection(ITEM, SELECTION)
        store.set_value('queue', 'movie', True)
        poster = {'id': 1, 'url': SELECTION['series_poster_url'], 'preview_needs_load': True, 'title': 'Poster'}
        jpeg = io.BytesIO()
        Image.new('RGB', (160, 240), '#42566a').save(jpeg, 'JPEG')
        for name, value in {
            'app.scraper.get_jellyfin_items': [ITEM, movie],
            'app.scraper.get_jellyfin_server_info': {'name': 'Offline smoke library', 'connected': True},
            'app.scraper.get_jellyfin_libraries': [],
            'app.scraper.get_jellyfin_seasons': [{'id': 'season', 'title': 'Season 1', 'number': 1, 'has_poster': False}],
            'app.scraper.search_tpdb_for_poster_groups': {'posters': [poster], 'groups': [], 'best_group': None},
            'app.scraper.fetch_tpdb_image': (jpeg.getvalue(), 'image/jpeg'),
            'app.fetch_image': (jpeg.getvalue(), 'image/jpeg'),
        }.items():
            stack.enter_context(patch(name, return_value=value))
        server = make_server('127.0.0.1', 0, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        stack.callback(server.shutdown)
        options = Options()
        options.binary_location = args.browser
        options.add_argument('--headless=new')
        options.add_argument('--window-size=1280,1000')
        options.add_argument('--disable-background-networking')
        options.add_argument('--disable-gpu')
        options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
        driver = webdriver.Chrome(service=Service(args.driver), options=options)
        stack.callback(driver.quit)
        driver.set_page_load_timeout(20)
        driver.set_script_timeout(10)
        driver.execute_cdp_cmd('Network.enable', {})
        driver.execute_cdp_cmd('Network.setBlockedURLs', {'urls': ['https://theposterdb.com/*', 'https://images.theposterdb.com/*', 'http://jellyfin.test/*']})
        wait = WebDriverWait(driver, 20)
        driver.get(f'http://127.0.0.1:{server.server_port}')
        wait.until(lambda d: d.execute_script("return typeof bootstrap !== 'undefined' && document.getElementById('selectedCount').textContent === '1'"))
        assert driver.execute_script("return manualQueueIds.has('movie')")
        driver.execute_script("sortContent('year')")
        wait.until(lambda d: 'sort=year' in d.current_url and d.execute_script("return document.getElementById('selectedCount').textContent === '1'"))
        driver.execute_script("enqueuePosterJob({kind:'manual', item_ids:['show']})")
        wait.until(lambda d: len(store.jobs()) == 1)
        job = store.jobs()[0]
        with patch.object(service, 'upload', side_effect=[True, False]):
            queue.run(job['job_id'])
        wait.until(lambda d: d.execute_script("return document.getElementById('failedItemsCount').textContent === '1'"))
        remaining = store.selections()['show']['selection']
        assert not remaining.get('series_poster_url')
        assert remaining['season_posters']
        driver.execute_script("enqueuePosterJob({kind:'retry', item_ids:['show']})")
        wait.until(lambda d: len(store.jobs()) == 2)
        retry = store.jobs()[0]
        with patch.object(service, 'upload', return_value=True) as upload:
            queue.run(retry['job_id'])
            assert upload.call_count == 1
        wait.until(lambda d: d.execute_script("return document.getElementById('selectedCount').textContent === '0' && document.getElementById('failedItemsCount').textContent === '0'"))
        print('Browser: selection restore and partial-target retry passed.', flush=True)
        driver.execute_script("loadPosters('movie')")
        wait.until(lambda d: d.execute_script("const image = document.querySelector('#posterModal .poster-image'); return image?.naturalWidth > 0 && image.src.includes('/thumbnail?')"))
        wait.until(lambda d: d.execute_script("return document.getElementById('posterModal').classList.contains('show') && !posterModal._isTransitioning"))
        driver.execute_script('posterModal.hide()')
        driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
        wait.until(lambda d: d.execute_script("return getComputedStyle(document.getElementById('posterModal')).display === 'none'"))
        assert driver.execute_script('return window.innerWidth === 390 && document.documentElement.scrollWidth <= 390'), 'Mobile page overflows'
        if args.screenshot:
            driver.execute_script("document.querySelectorAll('.toast').forEach(toast => toast.remove()); document.getElementById('jobQueuePanel').scrollIntoView()")
            driver.save_screenshot(args.screenshot)
        errors = [entry for entry in driver.get_log('browser') if entry['level'] == 'SEVERE' and entry.get('source') == 'javascript']
        assert not errors, errors
        print('Browser smoke passed: restore, sort, partial upload, exact retry, lazy preview, mobile layout, no JS errors.')


if __name__ == '__main__':
    main()
