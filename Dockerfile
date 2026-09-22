FROM odoo:19.0

USER root

COPY custom_addons /mnt/extra-addons

RUN pip3 install --no-cache-dir requests

USER odoo
