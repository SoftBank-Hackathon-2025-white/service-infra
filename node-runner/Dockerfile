FROM node:18-slim

WORKDIR /runner

COPY package*.json ./
RUN npm install

COPY run.js /runner/run.js

CMD ["node", "run.js"]