#!/bin/sh
# Create the release bucket and the versioned site source bucket, a read-write user for websites
# and a user for children that can only read releases (child-policy.json), never sources.
set -eu
root="http://$(cat /rustfs/access):$(cat /rustfs/secret)@rustfs:9000"
export MC_HOST_r="$root"
until mc ls r >/dev/null 2>&1; do sleep 1; done
mc mb --ignore-existing r/releases
mc mb --ignore-existing r/sources
mc version enable r/sources
mc admin policy create r releases-read /deploy/child-policy.json
mc admin user add r "$(cat /websites/storage_access)" "$(cat /websites/storage_secret)"
mc admin policy attach r readwrite --user "$(cat /websites/storage_access)"
mc admin user add r "$(cat /child/storage_access)" "$(cat /child/storage_secret)"
mc admin policy attach r releases-read --user "$(cat /child/storage_access)"
echo "storage ready"
