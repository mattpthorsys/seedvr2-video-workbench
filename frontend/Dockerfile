FROM node:22-bookworm-slim AS build

WORKDIR /app
COPY frontend/package.json ./package.json
RUN npm install
COPY frontend/angular.json frontend/tsconfig.json frontend/tsconfig.app.json ./
COPY frontend/src ./src
RUN npm run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/seedvr2-video-workbench/browser /usr/share/nginx/html

