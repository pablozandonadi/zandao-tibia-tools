#!/usr/bin/env bash
# Implanta a Mensagem automática na VM Oracle em modo teste (transporte fake). Idempotente:
# reexecutar não regera segredos, não reformata o volume e não mexe no contêiner piratas-whatsapp.
# Uso (na VM): sudo bash zt-deploy.sh /tmp/zt-src.tar /tmp/message-bridge
set -euo pipefail
IP=140.238.185.24
SRC_TAR=$1
BRIDGE_BIN=$2
APP=/opt/zandaotools
SVC=$APP/server/message-automation
CB=/opt/certbot/bin/certbot
LIVE=/etc/letsencrypt/live/zt-automation
VOL=/var/lib/zt-whatsapp-volume/sessions.luks
LUKS_KEY=/etc/zt-whatsapp/luks.key

echo "== 1. firewall da VM: libera 80/443 antes do REJECT"
for p in 80 443; do
  if ! iptables -C INPUT -p tcp -m state --state NEW -m tcp --dport $p -m comment --comment zt-https -j ACCEPT 2>/dev/null; then
    pos=$(iptables -L INPUT --line-numbers -n | awk '$2=="REJECT"{print $1; exit}')
    iptables -I INPUT "${pos:?REJECT nao encontrado}" -p tcp -m state --state NEW -m tcp --dport $p -m comment --comment zt-https -j ACCEPT
  fi
done
test -f /etc/iptables/rules.v4
grep -q zt-https /etc/iptables/rules.v4 || sed -i '0,/^-A INPUT -j REJECT/s//-A INPUT -p tcp -m state --state NEW -m tcp --dport 80 -m comment --comment zt-https -j ACCEPT\n-A INPUT -p tcp -m state --state NEW -m tcp --dport 443 -m comment --comment zt-https -j ACCEPT\n&/' /etc/iptables/rules.v4

echo "== 2. pacotes"
DEBIAN_FRONTEND=noninteractive apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx python3-venv openssl cryptsetup >/dev/null
if [ ! -x $CB ]; then
  python3 -m venv /opt/certbot
  /opt/certbot/bin/pip install -q --upgrade pip
  /opt/certbot/bin/pip install -q 'certbot>=5.4'
fi
$CB --version
$CB --help all | grep -q -- --ip-address || { echo "certbot sem suporte a certificado por IP"; exit 1; }

write_nginx() {
  install -d -m 0755 /var/www/zt-acme
  cat > /etc/nginx/sites-available/zt-automation <<'EOF'
server {
    listen 80 default_server;
    server_name _;
    access_log off;
    location ^~ /.well-known/acme-challenge/ { root /var/www/zt-acme; default_type text/plain; }
    location / { return 404; }
}
EOF
  if [ -e $LIVE/fullchain.pem ]; then
    cat >> /etc/nginx/sites-available/zt-automation <<'EOF'
server {
    listen 443 ssl default_server;
    server_name _;
    ssl_certificate /etc/letsencrypt/live/zt-automation/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zt-automation/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    access_log off;
    client_max_body_size 32k;
    location / {
        proxy_pass http://127.0.0.1:8787;
        proxy_set_header Host $host;
        proxy_read_timeout 60s;
    }
}
EOF
  fi
  rm -f /etc/nginx/sites-enabled/default
  ln -sf ../sites-available/zt-automation /etc/nginx/sites-enabled/zt-automation
  nginx -t -q
  systemctl reload nginx
}

echo "== 3. nginx HTTP (só desafio do certificado)"
write_nginx

echo "== 4. certificado HTTPS no IP (staging primeiro, depois o real)"
if [ ! -e $LIVE/fullchain.pem ]; then
  args=(certonly --webroot -w /var/www/zt-acme --ip-address $IP --preferred-profile shortlived
        --non-interactive --agree-tos --register-unsafely-without-email --cert-name zt-automation)
  $CB "${args[@]}" --dry-run
  $CB "${args[@]}"
fi
conf=/etc/letsencrypt/renewal/zt-automation.conf
grep -q '^renew_before_expiry' $conf || sed -i '0,/^\[renewalparams\]/s//renew_before_expiry = 2 days\n&/' $conf
cat > /etc/systemd/system/zt-certbot.service <<'EOF'
[Unit]
Description=Renova o certificado HTTPS da Mensagem automatica
[Service]
Type=oneshot
ExecStart=/opt/certbot/bin/certbot renew -q --deploy-hook "systemctl reload nginx"
EOF
cat > /etc/systemd/system/zt-certbot.timer <<'EOF'
[Timer]
OnCalendar=*-*-* 00,12:00:00
RandomizedDelaySec=1h
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now zt-certbot.timer
write_nginx

echo "== 5. usuários, código e venv"
id zt-automation >/dev/null 2>&1 || useradd --system --home /nonexistent --shell /usr/sbin/nologin zt-automation
id zt-whatsapp >/dev/null 2>&1 || useradd --system --home /nonexistent --shell /usr/sbin/nologin zt-whatsapp
install -d -m 0755 -o root -g root $APP
tar -xf "$SRC_TAR" -C $APP --no-same-owner
install -m 0755 -o root -g root "$BRIDGE_BIN" $SVC/message-bridge
chown -R root:root $APP
chmod -R go-w,o+rX $APP
[ -x $SVC/.venv/bin/python ] || python3 -m venv $SVC/.venv
$SVC/.venv/bin/pip install -q -r $SVC/requirements.txt

echo "== 6. segredos (só cria se não existirem; nada é impresso)"
install -d -m 0750 -o root -g zt-automation /etc/zt-automation
install -d -m 0750 -o root -g zt-whatsapp /etc/zt-whatsapp
(
  umask 077
  [ -s /etc/zt-automation/data.key ] || $SVC/.venv/bin/python -c "from cryptography.fernet import Fernet;open('/etc/zt-automation/data.key','wb').write(Fernet.generate_key())"
  [ -s /etc/zt-automation/bridge.token ] || openssl rand -hex 32 > /etc/zt-automation/bridge.token
)
chown root:zt-automation /etc/zt-automation/data.key /etc/zt-automation/bridge.token
chmod 0640 /etc/zt-automation/data.key /etc/zt-automation/bridge.token
[ -s /etc/zt-whatsapp/bridge.token ] || install -m 0640 -o root -g zt-whatsapp /etc/zt-automation/bridge.token /etc/zt-whatsapp/bridge.token
[ -e /etc/zt-automation/service.env ] || install -m 0640 -o root -g zt-automation $SVC/deploy/service.env.example /etc/zt-automation/service.env
[ -e /etc/zt-whatsapp/bridge.env ] || install -m 0640 -o root -g zt-whatsapp $SVC/deploy/bridge.env.example /etc/zt-whatsapp/bridge.env

echo "== 7. volume cifrado (LUKS) para as sessões do WhatsApp"
install -d -m 0700 /var/lib/zt-whatsapp-volume
if [ ! -e $VOL ]; then
  [ ! -e $LUKS_KEY ] || { echo "chave LUKS existe sem volume: parar e revisar"; exit 1; }
  (umask 077; head -c 64 /dev/urandom > $LUKS_KEY)
  fallocate -l 1G $VOL
  chmod 0600 $VOL
  cryptsetup luksFormat --batch-mode --type luks2 $VOL --key-file $LUKS_KEY
  cryptsetup open $VOL zt-whatsapp --key-file $LUKS_KEY
  mkfs.ext4 -q /dev/mapper/zt-whatsapp
fi
chown root:root $LUKS_KEY
chmod 0400 $LUKS_KEY
grep -q '^zt-whatsapp ' /etc/crypttab 2>/dev/null || echo "zt-whatsapp $VOL $LUKS_KEY luks" >> /etc/crypttab
grep -q ' /var/lib/zt-whatsapp ' /etc/fstab || echo "/dev/mapper/zt-whatsapp /var/lib/zt-whatsapp ext4 defaults,nofail 0 2" >> /etc/fstab
install -d -m 0700 /var/lib/zt-whatsapp
systemctl daemon-reload
[ -e /dev/mapper/zt-whatsapp ] || cryptsetup open $VOL zt-whatsapp --key-file $LUKS_KEY
mountpoint -q /var/lib/zt-whatsapp || mount /var/lib/zt-whatsapp
chown zt-whatsapp:zt-whatsapp /var/lib/zt-whatsapp
chmod 0700 /var/lib/zt-whatsapp

echo "== 8. serviços: API ligada em modo teste; ponte e agenda instaladas, paradas"
install -m 0644 $SVC/deploy/zt-automation-api.service $SVC/deploy/zt-automation-worker.service \
  $SVC/deploy/zt-automation-worker.timer $SVC/deploy/zt-whatsapp-bridge.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable zt-automation-api.service
systemctl restart zt-automation-api.service
sleep 3
systemctl is-active zt-automation-api.service
curl -fsS http://127.0.0.1:8787/health; echo
echo "== OK"
