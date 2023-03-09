FROM arm64v8/ubuntu:22.10

# Update repositories and install apt packages
RUN apt update -y && apt install curl -y
RUN curl -s https://deb.nodesource.com/setup_16.x | bash
RUN apt update -y && apt install libmariadb3 libmariadb-dev python3 python3-pip nodejs npm -y

# Copy backend and install pip requirements
COPY backend /backend
RUN pip install -r /backend/requirements.txt
EXPOSE 5000

# Copy frontend and install npm packages
COPY frontend /frontend
COPY frontend/package.json /frontend/package.json
RUN ln -s /emulation /frontend/src/assets/emulation
WORKDIR  /frontend
RUN npm install
EXPOSE 5173

CMD ["/bin/bash", "-c", "python3 /backend/src/main.py & cd /frontend && npm run dev"]
