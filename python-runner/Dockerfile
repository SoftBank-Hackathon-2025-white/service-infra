FROM node:18-slim

WORKDIR /runner

COPY app.js .

RUN npm init -y && npm install express aws-sdk

EXPOSE 8080

CMD ["node", "app.js"]