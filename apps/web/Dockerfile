FROM node:22-slim AS build
WORKDIR /repo
COPY packages/types packages/types
COPY apps/web apps/web
WORKDIR /repo/apps/web
ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=$API_INTERNAL_URL
RUN npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund
RUN npm run build
EXPOSE 3000
ENV NODE_ENV=production
CMD ["npm", "run", "start"]
