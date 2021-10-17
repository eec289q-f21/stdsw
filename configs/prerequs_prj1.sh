#!/bin/bash
eec_user=$(whoami)
home_dir="$(eval echo ~"$eec_user")"

function updates {
	sudo apt-get update
	sudo apt-get install -y  linux-tools-5.4.0-88-generic  linux-tools-generic
	set -e

	if [[ $EUID -ne 0 ]]; then
	   sudo -E $0
	else
	   echo "Giving everyone access to kernel perf counters"
	   if ! grep -q "kernel.perf_event_paranoid = 0" /etc/sysctl.conf; then
	      echo "kernel.perf_event_paranoid = 0" >> /etc/sysctl.conf
	   fi
	fi
	
	sudo sh -c 'echo 0 >/proc/sys/kernel/perf_event_paranoid'
}

export -f updates

if declare -f "$1" > /dev/null
then
	# call the function
	"$@"
else
	sudo bash -c "$(declare -f updates); updates"
fi
