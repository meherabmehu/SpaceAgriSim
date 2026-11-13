FROM node:24-alpine AS build
WORKDIR /web
# No package.json is copied, because the repository does not hold one. scripts/npm.mjs writes the
# manifests npm needs into /tmp/spaceagrisim-frontend (outside the copied source tree) and removes
# them once `npm ci` returns.
COPY frontend/ ./
RUN node scripts/npm.mjs ci && node scripts/npm.mjs build

FROM nginx:stable-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80
