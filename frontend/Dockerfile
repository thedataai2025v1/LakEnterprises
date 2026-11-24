# ==============================================================================
# Dockerfile for LakEnterprises Next.js Console UI Shell (:3001)
# Node.js 22 Alpine Multi-Stage
# ==============================================================================

FROM node:22-alpine AS base

WORKDIR /app

# Install dependencies
COPY frontend/package.json ./
RUN npm install

# Copy application source
COPY frontend/ ./

EXPOSE 3001

ENV PORT=3001
ENV NODE_ENV=development

CMD ["npm", "run", "dev"]
