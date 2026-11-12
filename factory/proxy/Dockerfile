# The only way out of the agent networks: a forward proxy that allows a short list of hosts.
FROM alpine:3.22
RUN apk add --no-cache tinyproxy
COPY tinyproxy.conf allowed-hosts /etc/tinyproxy/
EXPOSE 8888
CMD ["tinyproxy", "-d", "-c", "/etc/tinyproxy/tinyproxy.conf"]
