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
from selenium.webdriver.common.action_chains import ActionChains
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


def start(profile, offline=False, proxy=None, unsigned=False):
    options = Options()
    if os.environ.get('FIREFOX_BINARY'):
        options.binary_location = os.environ['FIREFOX_BINARY']
    options.add_argument('-headless')
    if unsigned:
        options.set_preference('xpinstall.signatures.required', False)
    if offline or proxy:
        options.set_preference('network.proxy.type', 1)
        options.set_preference('network.proxy.http', '127.0.0.1')
        options.set_preference('network.proxy.http_port', proxy or 9)
        options.set_preference('network.proxy.ssl', '127.0.0.1')
        options.set_preference('network.proxy.ssl_port', proxy or 9)
        options.set_preference('network.proxy.no_proxies_on', 'localhost,127.0.0.1')
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


