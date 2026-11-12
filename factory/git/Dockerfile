# The git server for local delivery mode: one bare repository, reachable only over the git
# protocol, so the hooks below cannot be bypassed or edited by whoever pushes.
FROM alpine:3.22
RUN apk add --no-cache git git-daemon curl
COPY hooks/ /hooks/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /hooks/* /entrypoint.sh
EXPOSE 9418
ENTRYPOINT ["/entrypoint.sh"]
