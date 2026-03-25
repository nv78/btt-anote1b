FROM node:20-slim

WORKDIR /app

# Install dependencies first (better layer caching)
COPY package.json package-lock.json* ./
RUN npm install

# Copy source files
COPY . .

EXPOSE 3000

CMD ["npm", "start"]
