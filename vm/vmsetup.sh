#!/bin/bash
eec_user=$(whoami)
home_dir="$(eval echo ~"$eec_user")"

function install_opencilk {
        cd $home_dir
        file="./OpenCilk-1.0-LLVM-10.0.1-Ubuntu-20.04-x86_64.tar.gz"
	if [ -e $file ]; then
	  rm -rf ./OpenCilk-1.0-LLVM-10.0.1-Ubuntu-20.04-x86_64.tar.gz
	fi
	
	directory="./opencilk"
	if [ -d $directory ]; then
	  rm -rf ./opencilk
	fi
	
        wget https://github.com/OpenCilk/opencilk-project/releases/download/opencilk%2Fv1.0/OpenCilk-1.0-LLVM-10.0.1-Ubuntu-20.04-x86_64.tar.gz
        tar -zvxf ./OpenCilk-1.0-LLVM-10.0.1-Ubuntu-20.04-x86_64.tar.gz
        mv ./OpenCilk-10.0.1-Linux ./opencilk
        rm -rf ./OpenCilk-1.0-LLVM-10.0.1-Ubuntu-20.04-x86_64.tar.gz
        LLVM_BIN_PATH=$PWD/opencilk/bin
        LLVM_LIB_PATH=$PWD/opencilk/lib
        echo "export PATH=$PATH:$LLVM_BIN_PATH" >> ~/.bashrc
        echo "export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$LLVM_LIB_PATH" >> ~/.bashrc
}
export -f install_opencilk

function install_dev {
	if ! [ $(id -u) = 0 ]; then
	   echo "The script need to be run as root." >&2
	   exit 1
	fi
	
	if [ "$SUDO_USER" ]; then
	    real_user=$SUDO_USER
	else
	    real_user=$(whoami)
	fi
	
	apt-get update
	
	
     	apt-get install -y --no-install-recommends \
        apt-utils \
        nano \
        vim \
        curl \
        sudo \
        debhelper \
        build-essential \
        python3-setuptools \
        python3-all \
        python3-pip \
        wget \
        zlib1g-dev \
        libz3-dev \
        ninja-build \
        git \
        unzip \
        cmake \
        gdb \
        jq \
        awscli \
        valgrind \
        gcovr \
      	debian-keyring  \
      	debian-archive-keyring   \
      	apt-transport-https \
      	gnupg \
      	ca-certificates \
      	libc6-dev \
        linux-tools-common \
        linux-tools-aws \
        fakeroot

	rm -rf /var/lib/apt/lists
	
	pip3 install wheel
	
	pip3 install boto3
	
	pip3 install pyboto
	
	pip3 install stdeb==0.9.1
	
	pip3 install opentuner==0.8.3
}

if [[ $(lsb_release -rs) == "20.04" ]]; then
	sudo bash -c "$(declare -f install_dev); install_dev"
	su $eec_user -c "bash -c install_opencilk"
else
       echo "Non-compatible version"
fi

