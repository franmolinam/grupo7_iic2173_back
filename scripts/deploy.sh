#!/bin/bash
set -e

cd /home/ubuntu

# Login a ECR (ajusta REGION y REGISTRY si es necesario)
aws ecr get-login-password --region us-east-2 \
  | docker login --username AWS --password-stdin 127621463290.dkr.ecr.us-east-2.amazonaws.com

# Traer la imagen más reciente
docker pull 127621463290.dkr.ecr.us-east-2.amazonaws.com/cityexpress-api:latest

# Bajar y levantar con el compose de producción
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d