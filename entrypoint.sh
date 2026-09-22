#!/bin/bash

cat > /tmp/odoo.conf <<EOF
[options]
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons

db_host = ${ODOO_DATABASE_HOST}
db_port = ${ODOO_DATABASE_PORT}
db_user = ${ODOO_DATABASE_USER}
db_password = ${ODOO_DATABASE_PASSWORD}
EOF

exec odoo -c /tmp/odoo.conf
