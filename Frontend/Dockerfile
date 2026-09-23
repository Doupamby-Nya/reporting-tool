# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application (client + server)
RUN npm run build

# Production stage
FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install ONLY production dependencies
RUN npm ci --omit=dev

# Copy built files from builder
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/server-prod.js ./server.js

# Expose port
EXPOSE 3000

# Ensure the server binds to 0.0.0.0 inside the container
ENV HOST=0.0.0.0

# Run the production server
CMD ["node", "server.js"]