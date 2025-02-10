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

exec "$@"
