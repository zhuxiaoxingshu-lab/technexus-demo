#!/usr/bin/env bash
set -euo pipefail

certbot --nginx \
  -d yuanshuzhuan.cn \
  -d www.yuanshuzhuan.cn \
  --non-interactive \
  --agree-tos \
  --register-unsafely-without-email \
  --preferred-challenges http \
  --redirect

nginx -t
systemctl reload nginx
systemctl disable --now technexus-certbot-bootstrap.timer || true

