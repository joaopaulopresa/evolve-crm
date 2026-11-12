FROM node:22-alpine AS deps
WORKDIR /srv/web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# Built only by the pipeline checks: docker build --target test web
FROM deps AS test
RUN npm run lint && npm test

FROM deps AS build
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /srv/web/dist /usr/share/nginx/html
