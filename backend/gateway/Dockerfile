FROM nginx:1.27-alpine

# The nginx:1.27 entrypoint runs envsubst on every *.template file under
# /etc/nginx/templates/ at container start, writing the result to
# /etc/nginx/conf.d/. The current template has no envsubst variables (the
# video-service is proxied directly to its Cloudflare hostname); we keep the
# templates path so future env-driven knobs are easy to wire in. No custom
# entrypoint.
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/nginx.conf
COPY api_gateway.conf.template /etc/nginx/templates/api_gateway.conf.template
COPY proxy_headers.inc /etc/nginx/conf.d/proxy_headers.inc

EXPOSE 80
