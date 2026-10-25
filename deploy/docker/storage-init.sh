#!/bin/sh
# Create the release bucket, a read-write user for websites and a read-only user for children.
set -eu
root="http://$(cat /rustfs/access):$(cat /rustfs/secret)@rustfs:9000"
export MC_HOST_r="$root"
until mc ls r >/dev/null 2>&1; do sleep 1; done
mc mb --ignore-existing r/releases
mc admin user add r "$(cat /websites/storage_access)" "$(cat /websites/storage_secret)"
mc admin policy attach r readwrite --user "$(cat /websites/storage_access)" || true
mc admin user add r "$(cat /child/storage_access)" "$(cat /child/storage_secret)"
mc admin policy attach r readonly --user "$(cat /child/storage_access)" || true
echo "storage ready"
