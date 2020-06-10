
# All:      see README.md

# Build:    sudo docker build -t hugbot .
# Execute:  sudo docker run -it --env DISCORD_BOT_SECRET=yourTokenHere --name hugbot --mount type=bind,src=$PWD/log,dst=/home/log hugbot
# Clean:    sudo docker stop hugbot; sudo docker rm hugbot
# C.-Shell: sudo docker exec -it hugbot bash
# C.-Proc.: sudo docker top hugbot


FROM python:3.8.2

WORKDIR /home

# Cache pip dependencies layer separately
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Fonts layer
COPY *.ttf /usr/share/fonts/truetype/
RUN fc-cache -f -v

COPY . .

ENTRYPOINT [ "sh", "run_public.sh" ]
