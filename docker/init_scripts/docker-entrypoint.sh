#!/usr/bin/env bash

# Load environment variables from variants with a _FILE suffix.
# The following logic reads variables with a _FILE suffix and
# loads the contents of the file specified in the variable
# into the variable without the suffix.
for var_name in $(printenv | cut -d= -f1 | grep "_FILE$" || true); do
	# If variable is empty, skip.
	if [[ -z ${!var_name} ]]; then
		continue
	fi

	var_name_no_suffix=${var_name%"_FILE"}

	# If the variable without the suffix is already set, raise an error.
	if [[ -n ${!var_name_no_suffix} ]]; then
		echo "ERROR: Both ${var_name_no_suffix} and ${var_name} are set (but are exclusive)" >&2
		exit 1
	fi

	file_path="${!var_name}"

	# If file does not exist, raise an error.
	if [[ ! -f ${file_path} ]]; then
		echo "ERROR: File ${file_path} from ${var_name} does not exist" >&2
		exit 1
	fi

	echo "Setting ${var_name_no_suffix} from ${var_name} at ${file_path}"
	export "${var_name_no_suffix}"="$(cat "${file_path}")"

	# Unset the _FILE variable.
	unset "${var_name}"
done

# Set default values for environment variables used by nginx templates.
# Nginx uses `envsubst` to load environment variables into configuration files, but it does not
# support the default value syntax `${VAR:-default}`.
export ROMM_BASE_PATH=${ROMM_BASE_PATH:-/romm}
export ROMM_PORT=${ROMM_PORT:-8080}
# Keep the nginx upstream port in sync with the port gunicorn binds to.
export DEV_PORT=${DEV_PORT:-5000}

# Disable nginx access logs when log level is WARNING, ERROR, or CRITICAL
loglevel="${LOGLEVEL:-INFO}"
loglevel="${loglevel^^}"
case "${loglevel}" in
WARNING | WARN | ERROR | CRITICAL)
	export NGINX_ACCESS_LOG="access_log off;"
	;;
*)
	export NGINX_ACCESS_LOG=""
	;;
esac

# Set IPV6_LISTEN based on IPV4_ONLY
if [[ ${IPV4_ONLY} == "true" ]]; then
	export IPV6_LISTEN="#listen [::]:${ROMM_PORT};"
else
	export IPV6_LISTEN="listen [::]:${ROMM_PORT};"
fi

# Replace environment variables used in nginx configuration templates.
/docker-entrypoint.d/20-envsubst-on-templates.sh >/dev/null

# Fix symbolic links used by nginx for resources,
# if they don't point to the correct location,
# set by the ROMM_BASE_PATH environment variable.
if [[ -L /var/www/html/assets/romm/resources ]]; then
	target=$(readlink "/var/www/html/assets/romm/resources")

	# If the target is not the same as ${ROMM_BASE_PATH}/resources, recreate the symbolic link.
	if [[ ${target} != "${ROMM_BASE_PATH}/resources" ]]; then
		rm "/var/www/html/assets/romm/resources"
		ln -s "${ROMM_BASE_PATH}/resources" "/var/www/html/assets/romm/resources"
	fi
fi

exec "$@"
