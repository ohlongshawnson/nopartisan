"""Isolated Firefox integration checks; requires selenium and geckodriver.

AMO_XPI must point to the original signed 0.3.0 XPI. No existing user profile
is opened. Fixture checks use a temporary unsigned copy with localhost added
and only the hostname routing changed. They are NOT authenticated X evidence.
"""
import functools
import http.server
import json
import os
from pathlib import Path
import tempfile
import threading
import zipfile

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]
ID = 'nopartisan@ohlongshawnson.github.io'
RESULTS = []


def check(label, value):
    assert value, label
    RESULTS.append(label)
    print('PASS', label, flush=True)


def start(profile):
    options = Options()
    options.add_argument('-headless')
    options.add_argument('-profile')
    options.add_argument(str(profile))
    # Chrome context is needed only to locate the test extension's options URL
    # and to simulate a grant in this disposable test profile.
    os.environ['MOZ_REMOTE_ALLOW_SYSTEM_ACCESS'] = '1'
    return webdriver.Firefox(options=options, service=Service(os.environ.get('GECKODRIVER', 'geckodriver'), log_output=os.devnull))


def options_page(driver, addon_id=ID):
    driver.set_context('chrome')
    url = driver.execute_script('return WebExtensionPolicy.getByID(arguments[0]).getURL("options.html")', addon_id)
    driver.set_context('content')
    driver.get(url)
    WebDriverWait(driver, 10).until(lambda d: d.find_element('id', 'save').is_enabled())
    return url


def extension_async(driver, expression):
    return driver.execute_async_script('const done=arguments[0]; (async()=>(' + expression + '))().then(done,e=>done({error:String(e)}));')


def hidden(driver, selector):
    return driver.execute_script('return getComputedStyle(document.querySelector(arguments[0])).display === "none"', selector)


with tempfile.TemporaryDirectory(prefix='nopartisan-firefox-') as work:
    work = Path(work)
    profile = work / 'signed-profile'; profile.mkdir()
    driver = start(profile)
    try:
        driver.install_addon(str(Path(os.environ['AMO_XPI']).resolve()), temporary=False)
        options_page(driver)
        data = extension_async(driver, "Promise.all([browser.permissions.getAll(),browser.storage.local.get(),fetch(browser.runtime.getURL('keywords.json')).then(r=>r.json())]).then(([permissions,storage,list])=>({permissions,storage,count:list.keywords.length,mikeLee:NOpartisan.matcher(list.keywords)('Mike Lee spoke'),markLevin:NOpartisan.matcher(list.keywords)('Mark Levin spoke')}))")
        check('signed 0.3.0 fresh storage and bundled list available without GitHub access', data['storage'] == {} and data['count'] == 869 and 'https://raw.githubusercontent.com/*' not in data['permissions']['origins'])
        check('signed bundled matcher accepts Mike Lee; Mark Levin is absent', data['mikeLee'] and not data['markLevin'])
        check('signed fresh Firefox grants the three declared filtering sites', set(data['permissions']['origins']) == {'https://x.com/*', 'https://www.reddit.com/*', 'https://www.facebook.com/*'})
        driver.get('https://x.com/MikeLeeforUtah')
        print('LIVE X:', driver.current_url, 'tweet articles:', len(driver.find_elements('css selector', 'article[data-testid="tweet"]')), flush=True)
        # No claim of live filtering follows from a page with no available posts.
    finally:
        driver.quit()
    driver = start(profile)
    try:
        options_page(driver)
        check('signed installation and bundled list survive Firefox restart', '869 unique keywords' in driver.find_element('id', 'listInfo').text)
    finally:
        driver.quit()

    fixture = work / 'fixture'; fixture.mkdir()
    (fixture / 'index.html').write_text('<!doctype html><body><article id="political" data-testid="tweet">Mike Lee spoke today</article><article id="neutral" data-testid="tweet">A garden today</article><article id="custom" data-testid="tweet">Mark Levin spoke today</article></body>')
    (fixture / 'reddit.html').write_text('<!doctype html><body><shreddit-post id="political">Mike Lee spoke today</shreddit-post><shreddit-post id="neutral">A garden today</shreddit-post></body>')
    (fixture / 'facebook.html').write_text('<!doctype html><body><div role="feed"><div role="article" id="political">Mike Lee spoke today</div><div role="article" id="neutral">A garden today</div></div></body>')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(fixture))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = 'http://127.0.0.1/*'
    url = f'http://127.0.0.1:{server.server_port}/'
    addon_id = 'nopartisan-fixture@test.invalid'
    archive = work / 'fixture.xpi'
    with zipfile.ZipFile(archive, 'w') as out:
        for file in (ROOT / 'extension').iterdir():
            blob = file.read_bytes()
            if file.name == 'manifest.json':
                manifest = json.loads(blob)
                manifest['browser_specific_settings']['gecko']['id'] = addon_id
                manifest['host_permissions'].append(origin)
                manifest['content_scripts'][0]['matches'].append(origin)
                manifest['web_accessible_resources'][0]['matches'].append(origin)
                blob = json.dumps(manifest).encode()
            if file.name == 'content.js':
                text = blob.decode().replace("location.hostname === 'x.com'", "location.hostname === '127.0.0.1' && location.pathname === '/'")
                text = text.replace("const selectors = {", "const selectors = { '127.0.0.1': location.pathname === '/reddit.html' ? 'shreddit-post, div[data-testid=\"post-container\"]' : location.pathname === '/facebook.html' ? '[role=\"feed\"] [role=\"article\"]' : X.candidateSelector,")
                blob = text.encode()
            out.writestr(file.name, blob)
    profile = work / 'fixture-profile'; profile.mkdir()
    driver = start(profile)
    try:
        driver.install_addon(str(archive), temporary=True)
        options_url = options_page(driver, addon_id)
        check('development options reports granted website access', 'X: Access granted' in driver.find_element('id', 'siteAccess').text)
        driver.get(url)
        WebDriverWait(driver, 10).until(lambda d: hidden(d, '#political'))
        check('Firefox fixture: default bundled filtering uses actual CSS', hidden(driver, '#political') and not hidden(driver, '#neutral') and not hidden(driver, '#custom'))
        feed = driver.current_window_handle
        driver.switch_to.new_window('tab'); driver.get(options_url)
        WebDriverWait(driver, 10).until(lambda d: d.find_element('id', 'save').is_enabled())
        settings = driver.current_window_handle
        driver.find_element('id', 'custom').send_keys('Mark Levin')
        driver.find_element('id', 'save').click()
        WebDriverWait(driver, 10).until(lambda d: 'Settings saved' in d.find_element('id', 'status').text)
        driver.switch_to.window(feed)
        WebDriverWait(driver, 10).until(lambda d: hidden(d, '#custom'))
        check('Firefox fixture: options form synchronizes custom keyword to open tab', hidden(driver, '#custom'))
        driver.execute_script("document.querySelector('#political').previousElementSibling.querySelector('button').click()")
        check('Firefox fixture: Reveal restores computed visibility', not hidden(driver, '#political'))
        driver.execute_script("document.body.insertAdjacentHTML('beforeend','<article id=dynamic data-testid=tweet>Mike Lee again</article>')")
        WebDriverWait(driver, 10).until(lambda d: hidden(d, '#dynamic'))
        check('Firefox fixture: dynamically inserted posts filter', hidden(driver, '#dynamic'))
        driver.switch_to.window(settings)
        extension_async(driver, "browser.storage.local.get('settings').then(({settings})=>browser.storage.local.set({settings:{...settings,enabled:false}}))")
        driver.switch_to.window(feed)
        WebDriverWait(driver, 10).until(lambda d: not hidden(d, '#dynamic'))
        check('Firefox fixture: disabling restores all posts', all(not hidden(driver, s) for s in ['#political','#custom','#dynamic']))
        driver.switch_to.window(settings)
        extension_async(driver, "browser.storage.local.get('settings').then(({settings})=>browser.storage.local.set({settings:{...settings,enabled:true}}))")
        driver.switch_to.window(feed)
        WebDriverWait(driver, 10).until(lambda d: hidden(d, '#dynamic'))
        check('Firefox fixture: re-enabling filters matching posts', hidden(driver, '#dynamic') and hidden(driver, '#custom'))
        driver.switch_to.window(settings)
        extension_async(driver, "browser.permissions.remove({origins:['http://127.0.0.1/*','https://x.com/*']})")
        WebDriverWait(driver, 10).until(lambda d: 'X: Access missing' in d.find_element('id', 'siteAccess').text)
        check('Firefox fixture: denied X access is reported in settings', 'X: Access missing' in driver.find_element('id', 'siteAccess').text)
        driver.switch_to.window(feed); driver.refresh()
        check('Firefox fixture: denied host access prevents injection', not hidden(driver, '#political') and not driver.find_elements('css selector', '.nopartisan-notice'))
        driver.set_context('chrome')
        result = driver.execute_async_script("const done=arguments[arguments.length-1]; const id=arguments[0]; ChromeUtils.importESModule('resource://gre/modules/ExtensionPermissions.sys.mjs').ExtensionPermissions.add(id,{origins:['http://127.0.0.1/*'],permissions:[]},WebExtensionPolicy.getByID(id).extension).then(()=>done(true),e=>done(String(e)))", addon_id)
        driver.set_context('content')
        check('Firefox fixture: simulated host grant succeeds', result is True)
        driver.refresh()
        WebDriverWait(driver, 10).until(lambda d: hidden(d, '#political'))
        check('Firefox fixture: granting access and refreshing restores injection', hidden(driver, '#political'))
        for site in ['reddit', 'facebook']:
            driver.get(url + site + '.html')
            WebDriverWait(driver, 10).until(lambda d: hidden(d, '#political'))
            check(f'Firefox fixture: {site} adapter smoke test', hidden(driver, '#political') and not hidden(driver, '#neutral'))
    finally:
        driver.quit(); server.shutdown()
print(json.dumps({'passed': RESULTS, 'authenticated_live_x_verified': False}, indent=2))
