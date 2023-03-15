FROM arm64v8/ubuntu:22.10

# Update repositories and install apt packages
RUN apt update -y && apt install curl -y
RUN curl -s https://deb.nodesource.com/setup_16.x | bash
RUN apt update -y && apt install libmariadb3 libmariadb-dev python3 python3-pip nodejs npm -y

# Copy backend and install pip requirements
COPY backend /backend
RUN rm -rf /backend/venv
RUN pip install -r /backend/requirements.txt
EXPOSE 5000

# Copy frontend and install npm packages
COPY frontend /frontend
COPY frontend/package.json /frontend/package.json
RUN rm -rf /frontend/node_modules
RUN rm -rf /frontend/assets/emulation
RUN ln -s /emulation /frontend/assets/emulation
WORKDIR  /frontend
RUN npm install
EXPOSE 5173

CMD ["/bin/bash", "-c", "cd /frontend && npm run dev & python3 /backend/src/main.py"]
