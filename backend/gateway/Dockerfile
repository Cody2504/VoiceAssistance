FROM nginx:1.27-alpine

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/nginx.conf
COPY api_gateway.conf /etc/nginx/conf.d/api_gateway.conf
COPY proxy_headers.inc /etc/nginx/conf.d/proxy_headers.inc

EXPOSE 80
