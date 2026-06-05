FROM node:20-slim AS app

WORKDIR /app
COPY package.json package-lock.json /app/
RUN npm ci
COPY . /app

CMD ["npm", "run", "dev"]
