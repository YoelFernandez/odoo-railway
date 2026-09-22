FROM odoo:19.0

USER root

COPY custom-addons /mnt/custom-addons
COPY entrypoint.sh /entrypoint-custom.sh

RUN chmod +x /entrypoint-custom.sh
RUN chown -R odoo:odoo /mnt/custom-addons

USER odoo

ENTRYPOINT ["/entrypoint-custom.sh"]
