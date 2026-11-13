# Mozilla Add-ons listing copy

## Name

NOpartisan

## Summary

Filter political content from social feeds, with no left and no right. NOpartisan works offline with a complete bundled keyword list; automatic keyword updates keep new installations current.

## Description

NOpartisan filters supported Reddit, X, and Facebook feed items using local whole-word and phrase matching. It treats political viewpoints alike and gives you control over personal keywords, placeholders, and global filtering.

Filtering starts with included political vocabulary and rules, including individual X trends explicitly categorized as Politics. New installs automatically retrieve keyword updates from GitHub after installation and every 24 hours while Firefox runs. You do not need to configure a URL or add personal keywords. Firefox asks for access to the update host, raw.githubusercontent.com, during installation.

Automatic updates can be switched off in settings. Existing update preferences, personal keywords and custom sources are preserved when upgrading. Local filtering works offline and if update access is revoked. Failed or invalid downloads keep the last valid filters and retry later. The permanent political foundation remains active even when a downloaded list contains only names.

Feed text, browsing history, personal keywords, and matched phrases stay in Firefox and are never sent to NOpartisan or GitHub. When you download a list, GitHub can see ordinary connection information such as your IP address and requested URL. Failed or invalid downloads leave the last valid list in place.

NOpartisan reads text and available accessible descriptions. It does not use OCR or general semantic classification. Political names and phrases may be missed, and broad terms can hide unrelated posts. Filtering can be paused or reversed, and placeholders can include a Reveal control.

## Categories

Privacy & Security

## Version note

The bundled list is the schema-1 snapshot in `keywords/politics.json`; the Firefox archive carries the identical `extension/keywords.json` file. Maintained data updates do not replace the signed extension binary.
