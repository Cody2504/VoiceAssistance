FROM nginx:1.27-alpine

# The nginx:1.27 entrypoint already runs envsubst on every *.template file
# under /etc/nginx/templates/ at container start, writing the result into
# /etc/nginx/conf.d/. We use that to make `VIDEO_UPSTREAM` swappable between
# `video-service:1101` (local docker network) and `jockey-vast:1101` (Tailscale
# hostname when video-service is rented on vast.ai). No custom entrypoint.
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/nginx.conf
COPY api_gateway.conf.template /etc/nginx/templates/api_gateway.conf.template
COPY proxy_headers.inc /etc/nginx/conf.d/proxy_headers.inc

EXPOSE 80
