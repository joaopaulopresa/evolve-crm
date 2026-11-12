# Backs up the database and the application's git history to S3-compatible storage (MinIO).
FROM cgr.dev/chainguard/minio-client:latest AS mc

FROM alpine:3.22
RUN apk add --no-cache postgresql16-client git supercronic
COPY --from=mc /usr/bin/mc /usr/local/bin/mc
COPY backup.sh restore.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/restore.sh \
    && git config --system --add safe.directory '*'
ENTRYPOINT ["backup.sh"]
CMD ["schedule"]
