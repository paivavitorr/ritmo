FROM node:22-alpine
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile --ignore-scripts
COPY . .
RUN pnpm nuxt prepare
EXPOSE 3000
CMD ["pnpm", "dev", "--host", "0.0.0.0"]
