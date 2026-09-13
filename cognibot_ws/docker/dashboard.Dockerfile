# Operator dashboard: build the Vite app, serve static files with nginx.
# Build context is the repository root: scripts/sync-scene.mjs copies the simulator's MJCF scene
# and meshes into the bundle for the free-look view.
FROM node:22-alpine AS build
WORKDIR /repo/dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY cognibot_ws/src/cognibot_sim/robots/so101 /repo/cognibot_ws/src/cognibot_sim/robots/so101
COPY cognibot_ws/src/cognibot_sim/scenes /repo/cognibot_ws/src/cognibot_sim/scenes
COPY dashboard ./
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /repo/dashboard/dist /usr/share/nginx/html
EXPOSE 80
