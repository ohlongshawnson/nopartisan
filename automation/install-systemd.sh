#!/bin/sh
# Install code and disabled units only. Run/test the service before enabling its timer.
set -eu
test "$(id -u)" -eq 0 || { echo 'Run this installer as root.' >&2; exit 2; }
task_source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -d -m 0755 /opt/nopartisan-automation/automation
for task_filename in __init__.py pipeline.py publish.py expanded.py publishing.json; do
    install -m 0644 "$task_source_dir/$task_filename" "/opt/nopartisan-automation/automation/$task_filename"
done
install -d -m 0700 /etc/nopartisan
install -m 0644 "$task_source_dir/systemd/nopartisan-publish.service" /etc/systemd/system/nopartisan-publish.service
install -m 0644 "$task_source_dir/systemd/nopartisan-publish.timer" /etc/systemd/system/nopartisan-publish.timer
systemctl daemon-reload
echo 'Installed publisher and units. Timer enablement is a separate step after a successful manual service run.'
