"""Real Firefox network/install/migration/restart checks in disposable profiles.

Only real requests to the maintained GitHub URL are allowed through the proxy.
The proxy delays CONNECT (without decrypting TLS) to prove bundled filtering
starts before the initial download. Set PERMANENT_TEST=1 with Firefox Developer
Edition to install the unsigned candidate persistently and test actual restart.
"""
import functools
import http.server
import json
import os
from pathlib import Path
import select
import socket
import tempfile
import threading
import zipfile
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from firefox_support import ROOT, ID, RESULTS, check, start, options_page, extension_async, hidden

GITHUB = 'https://raw.githubusercontent.com/*'
TEST_ID = 'nopartisan-updates@test.invalid'

class Tunnel(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_CONNECT(self):
        if self.path != 'raw.githubusercontent.com:443' or not self.server.allowed:
            self.send_error(502); return
        self.server.requests.append(self.path)
        self.server.gate.wait(10)
        try:
            upstream = socket.create_connection(('raw.githubusercontent.com', 443), timeout=10)
            self.send_response(200); self.end_headers()
            connections = [self.connection, upstream]
            self.server.connections.extend(connections)
            while True:
                readable, _, _ = select.select(connections, [], [], 20)
                if not readable: break
                for source in readable:
                    data = source.recv(65536)
                    if not data: return
                    (upstream if source is self.connection else self.connection).sendall(data)
        except OSError:
            pass
        finally:
            if 'upstream' in locals(): upstream.close()


def package(path, addon_id):
    with zipfile.ZipFile(path, 'w') as archive:
        for file in (ROOT/'extension').iterdir():
            blob = file.read_bytes()
            if file.name == 'manifest.json':
                manifest = json.loads(blob)
                manifest['browser_specific_settings']['gecko']['id'] = addon_id
                manifest['host_permissions'].append('http://127.0.0.1/*')
                manifest['content_scripts'][0]['matches'].append('http://127.0.0.1/*')
                manifest['web_accessible_resources'][0]['matches'].append('http://127.0.0.1/*')
                blob = json.dumps(manifest).encode()
            if file.name == 'content.js':
                blob = blob.decode().replace("location.hostname === 'x.com'", "location.hostname === '127.0.0.1'").replace('const selectors = {', "const selectors = { '127.0.0.1': X.candidateSelector,").encode()
            if file.name == 'background.js':
                blob = blob.decode().replace("documentUrlPatterns: ['https://x.com/*']", "documentUrlPatterns: ['https://x.com/*', 'http://127.0.0.1/*']").encode()
            archive.writestr(file.name, blob)


def state(driver):
    return extension_async(driver, 'browser.storage.local.get()')


def inspection(driver, selector, other_handles):
    ActionChains(driver).context_click(driver.find_element('css selector', selector)).perform()
    driver.set_context('chrome')
    WebDriverWait(driver, 10).until(lambda d: d.execute_script("return [...document.querySelectorAll('menuitem')].some(x=>x.getAttribute('label')==='NOpartisan: Why is this post visible?')"))
    driver.execute_script("[...document.querySelectorAll('menuitem')].find(x=>x.getAttribute('label')==='NOpartisan: Why is this post visible?').doCommand();document.getElementById('contentAreaContextMenu').hidePopup()")
    driver.set_context('content')
    WebDriverWait(driver, 10).until(lambda d: len(d.window_handles)>len(other_handles))
    driver.switch_to.window(next(h for h in driver.window_handles if h not in other_handles))
    WebDriverWait(driver, 10).until(lambda d: d.find_element('id','state').text.startswith('{'))
    result = json.loads(driver.find_element('id','state').text)
    driver.close()
    return result

with tempfile.TemporaryDirectory(prefix='nopartisan-updates-') as work:
    work = Path(work)
    (work/'index.html').write_text((ROOT/'tests/fixtures/x-alito-trend.html').read_text())
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(work)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    proxy = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Tunnel)
    proxy.allowed = True; proxy.gate = threading.Event(); proxy.requests = []; proxy.connections = []
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/'
    archive = work/'candidate.xpi'; package(archive, TEST_ID)
    profile = work/'online-profile'; profile.mkdir()
    permanent = os.environ.get('PERMANENT_TEST') == '1'
    driver = start(profile, proxy=proxy.server_port, unsigned=permanent)
    try:
        print('BROWSER', driver.capabilities['browserVersion'], 'persistent unsigned candidate:', permanent, flush=True)
        driver.install_addon(str(archive), temporary=not permanent)
        options_url = options_page(driver, TEST_ID)
        settings = driver.current_window_handle
        WebDriverWait(driver, 10).until(lambda d: state(d).get('updateStatus') == 'checking')
        before = state(driver)
        check('fresh install enables automatic updates and starts real default download with no configuration', before['settings']['autoUpdate'] and before['settings']['enabled'] and before['settings']['custom'] == [] and 'remoteList' not in before)
        granted = extension_async(driver, 'browser.permissions.getAll()')
        check('required HTTPS GitHub host permission granted on fresh Firefox install', GITHUB in granted['origins'])
        driver.switch_to.new_window('tab'); driver.get(url); feed = driver.current_window_handle
        WebDriverWait(driver, 10).until(lambda d: hidden(d, '#alito'))
        check('bundled Politics/Alito filtering starts while actual GitHub connection is delayed', hidden(driver,'#alito') and not hidden(driver,'#fursuit') and not hidden(driver,'#happening'))
        driver.switch_to.window(settings)
        check('download still pending after bundled filtering initialized', 'remoteList' not in state(driver))
        proxy.gate.set()
        WebDriverWait(driver, 25).until(lambda d: state(d).get('updateStatus') == 'current')
        downloaded = state(driver)
        foundation = json.loads((ROOT/'extension/foundational.json').read_text())['keywords']
        check('real GitHub TLS download validates, merges foundation and caches success atomically', bool(proxy.requests) and downloaded['downloadedKeywordCount'] > 800 and all(k in downloaded['remoteList']['keywords'] for k in foundation) and bool(downloaded['lastUpdate']) and downloaded['updateError'] == '')
        print('REAL DOWNLOAD', json.dumps({k:downloaded[k] for k in ['downloadedKeywordCount','lastUpdate','nextUpdate']}) ,flush=True)
        alarm = extension_async(driver, "browser.alarms.get('keywords')")
        check('next automatic check scheduled at the saved 24-hour due time', abs(alarm['scheduledTime']-downloaded['nextUpdate'])<1000)
        driver.switch_to.window(feed)
        report = inspection(driver, '#fursuit', set(driver.window_handles))
        check('existing content script automatically reevaluates using the downloaded cache', report['list']['source']=='downloaded' and report['list']['version']==downloaded['remoteList']['version'] and report['list']['personalKeywordCount']==0)
        driver.switch_to.window(settings)
        extension_async(driver, "browser.permissions.remove({origins:['https://raw.githubusercontent.com/*']})")
        denied = extension_async(driver, "browser.runtime.sendMessage({type:'update'})")
        check('revoked permission reports a local error and preserves the known-good cache', bool(denied.get('error')) and state(driver)['remoteList']==downloaded['remoteList'])
        WebDriverWait(driver, 10).until(lambda d: 'Update access is missing' in d.find_element('id','listInfo').text)
        driver.switch_to.window(feed)
        check('political filtering continues with update permission revoked', hidden(driver,'#alito') and not hidden(driver,'#fursuit'))
        driver.switch_to.window(settings)
        proxy.allowed = False
        for connection in list(proxy.connections):
            try: connection.shutdown(socket.SHUT_RDWR)
            except OSError: pass
        driver.set_context('chrome')
        driver.execute_async_script("const done=arguments[arguments.length-1];const id=arguments[0];ChromeUtils.importESModule('resource://gre/modules/ExtensionPermissions.sys.mjs').ExtensionPermissions.add(id,{permissions:[],origins:['https://raw.githubusercontent.com/*']},WebExtensionPolicy.getByID(id).extension).then(()=>done(true))", TEST_ID)
        driver.set_context('content')
        failed = extension_async(driver, "browser.runtime.sendMessage({type:'update'})")
        check('real network failure preserves cached filters and schedules a later retry', bool(failed.get('error')) and state(driver)['remoteList']==downloaded['remoteList'] and state(driver)['nextUpdate']<downloaded['nextUpdate'])
        # Restore a successful check so restart verifies the normal next-day schedule.
        proxy.allowed = True
        result = extension_async(driver, "browser.runtime.sendMessage({type:'update'})")
        check('real subsequent download recovers without configuration', bool(result.get('version')) and state(driver)['updateError']=='')
        saved = state(driver)
    finally:
        driver.quit()
    if permanent:
        driver = start(profile, proxy=proxy.server_port, unsigned=True)
        try:
            options_page(driver, TEST_ID)
            cached = state(driver)
            check('actual Firefox restart preserves cached keywords and automatic-update settings', cached['remoteList']==saved['remoteList'] and cached['settings']==saved['settings'])
            WebDriverWait(driver, 10).until(lambda d: extension_async(d, "browser.alarms.get('keywords')") is not None)
            alarm = extension_async(driver, "browser.alarms.get('keywords')")
            check('actual restart reschedules the saved next-day check without fetching early', cached['lastUpdate']==saved['lastUpdate'] and abs(alarm['scheduledTime']-saved['nextUpdate'])<1000)
            driver.get(url);WebDriverWait(driver, 10).until(lambda d: hidden(d,'#alito'))
            check('Politics/Alito filtering still works after actual Firefox restart', hidden(driver,'#alito') and not hidden(driver,'#fursuit'))
        finally:
            driver.quit()
    # Real upgrade from the original signed extension, preserving opt-out and custom configuration.
    profile = work/'migration-profile'; profile.mkdir()
    migration = work/'migration.xpi'; package(migration, ID)
    driver = start(profile, proxy=proxy.server_port, unsigned=permanent)
    try:
        driver.install_addon(str(Path(os.environ['AMO_XPI']).resolve()), temporary=False)
        options_page(driver)
        seed = {'settings': {'enabled':False,'showPlaceholders':False,'custom':['personal phrase'],'source':'https://raw.githubusercontent.com/team/nopartisan/main/custom.json','autoUpdate':False},'remoteList':{'schemaVersion':1,'version':'known-good','keywords':['cached phrase']},'lastUpdate':'2026-11-12T12:00:00.000Z'}
        extension_async(driver, 'browser.storage.local.set('+json.dumps(seed)+')')
        # Keep a normal page open: upgrading closes old extension pages.
        driver.switch_to.new_window('tab'); driver.get(url)
        driver.install_addon(str(migration), temporary=not permanent)
        options_page(driver)
        migrated = state(driver)
        check('actual upgrade preserves explicit opt-out, custom source, personal phrases, cache and disabled filtering', all(migrated[k]==v for k,v in seed.items()))
        check('opted-out upgrade schedules no automatic download', extension_async(driver, "browser.alarms.get('keywords')") is None and migrated.get('lastAttempt') is None)
    finally:
        driver.quit();server.shutdown();proxy.shutdown()
print(json.dumps({'passed':RESULTS,'authenticated_live_x_verified':False,'persistent_restart_tested':permanent},indent=2))
