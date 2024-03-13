#!/bin/bash

echo "Welcome to the RomM Installer!"

# Prompt for username
read -p "Enter a username: " username

# Prompt for password, or generate a random one if left blank
while true; do
    read -s -p "Enter a password (leave blank to generate a random one): " password
    echo
    if [ -z "$password" ]; then
        password=$(openssl rand -base64 32)
        echo "Random password generated: $password"
        break
    elif [ ${#password} -lt 8 ]; then
        echo "Password must be at least 8 characters long. Please try again."
    else
        break
    fi
done

# Prompt for the root of ROMs directory
read -p "Enter the root of your ROMs directory: " root

# Generate MySQL database password
mysql_password=$(openssl rand -base64 32)
echo "MySQL database password: $mysql_password"

# Generate MySQL admin database password
mysql_admin_password=$(openssl rand -base64 32)
echo "MySQL admin database password: $mysql_admin_password"

# Prompt for IGDB_CLIENT_ID and IGDB_CLIENT_SECRET
read -p "Enter your IGDB_CLIENT_ID: " igdb_client_id
read -p "Enter your IGDB_CLIENT_SECRET: " igdb_client_secret

# Confirm installation
read -p "Do you want to proceed with the installation? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "Installation canceled."
    exit 1
fi

# Update and upgrade packages
apt update -y && apt upgrade -y && apt install curl -y

# Check for Docker and install if not present
if ! command -v docker &> /dev/null; then
    echo "Docker not found, installing..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
fi

# Create docker-compose.yml file
cat << EOF > docker-compose.yml
version: "3"

volumes:
  mysql_data:
  romm_resources:
  romm_redis_data:

services:

  RomM:
    image: zurdi15/romm:latest
    container_name: RomM
    restart: unless-stopped
    environment:
      - DB_HOST=RomM-DB
      - DB_NAME=RomM
      - DB_USER=RomM
      - DB_PASSWD=$mysql_password
      - IGDB_CLIENT_ID=$igdb_client_id
      - IGDB_CLIENT_SECRET=$igdb_client_secret
      - ROMM_AUTH_SECRET_KEY=$(openssl rand -hex 32)
      - ROMM_AUTH_USERNAME=$username
      - ROMM_AUTH_PASSWORD=$password
    volumes:
      - romm_resources:/romm/resources
      - romm_redis_data:/redis-data
      - $root/Library:/romm/library
      - $root/Assets:/romm/assets
      - $root/:/romm/config
      - $root/LOGs:/romm/logs
    ports:
      - 80:8080
    depends_on:
      - RomM-DB

  RomM-DB:
    image: mariadb:latest
    container_name: RomM-DB
    restart: unless-stopped
    environment:
      - MYSQL_ROOT_PASSWORD=$mysql_admin_password
      - MYSQL_DATABASE=RomM
      - MYSQL_USER=RomM
      - MYSQL_PASSWORD=$mysql_password
    volumes:
      - mysql_data:/var/lib/mysql
EOF

# Run the docker-compose
docker compose up -d

echo "Installation completed!"
echo "Visit http://YOUR_SERVER_IP in your browser."
echo "Username: $username"
echo "Password: $password"
