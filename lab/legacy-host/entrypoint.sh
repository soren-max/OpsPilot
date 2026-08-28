#!/bin/sh
set -eu

mkdir -p /run/opspilot-keys /home/opspilot/.ssh
ssh-keygen -A
if [ ! -f /run/opspilot-keys/id_ed25519 ]; then
  ssh-keygen -q -t ed25519 -N '' -f /run/opspilot-keys/id_ed25519
fi
cp /run/opspilot-keys/id_ed25519.pub /home/opspilot/.ssh/authorized_keys
chown -R opspilot:opspilot /home/opspilot/.ssh
chmod 0700 /home/opspilot/.ssh
chmod 0600 /home/opspilot/.ssh/authorized_keys /run/opspilot-keys/id_ed25519

runuser -u opspilot -- /opt/opspilot-demo/services.sh start demo-api
runuser -u opspilot -- python /opt/opspilot-demo/legacy_server.py &
exec /usr/sbin/sshd -D -e
