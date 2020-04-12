# Build:    sudo docker build -t hugbot-release .
# Execute:  sudo docker run -it --env DISCORD_BOT_SECRET=yourTokenHere --name hugbot hugbot-release; sudo docker rm hugbot
# Stop:     sudo docker stop hugbot && sudo docker rm hugbot
# Inspect:  sudo docker exec -it hugbot bash

FROM python:3

WORKDIR /home

# Cache pip dependencies layer separately
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT [ "sh", "run_public.sh" ]
