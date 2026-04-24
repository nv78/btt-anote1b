FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm ci --legacy-peer-deps

COPY . .

ENV HOST=0.0.0.0
EXPOSE 3000

CMD ["npm", "start"]
