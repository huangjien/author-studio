FROM alpine/sqlite:latest

WORKDIR /app

RUN apk add --no-cache build-base git bash cmake openblas-dev lapack-dev 

COPY . .


RUN apk add --no-cache curl

RUN mkdir -p /usr/lib/sqlite3/ && \
    curl -L -o /usr/lib/sqlite3/vss0.so https://github.com/asg017/sqlite-vss/releases/download/v0.1.2/vss0.so && \
    curl -L -o /usr/lib/sqlite3/vector0.so https://github.com/asg017/sqlite-vss/releases/download/v0.1.2/vector0.so

