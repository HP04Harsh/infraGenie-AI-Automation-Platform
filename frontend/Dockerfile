FROM node:20-slim AS build

WORKDIR /app

COPY frontend/package.json frontend/yarn.lock ./
RUN yarn install --frozen-lockfile

COPY frontend/ .

EXPOSE 3000

CMD ["yarn", "start"]
