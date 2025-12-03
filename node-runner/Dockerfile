FROM node:18-slim

WORKDIR /runner

COPY package*.json ./
RUN npm install

COPY app.js /runner/app.js
CMD ["node", "app.js"]