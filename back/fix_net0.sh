#!/bin/bash
# from
# https://github.com/oneclickvirt/pve_lxc_images

for release_name in *; do
      echo "$release_name"
      pct create 101 "$release_name" -cores 6 -cpuunits 1014 -memory 26480 -swap 0 -rootfs local:10 -onboot 1 -features nesting=1
      pct start 101
      pct set 101 --net0 name=spiritlhl,ip=172.16.1.2/24,bridge=vmbr1,gw=172.16.1.1
      pct set 101 --delete net0
      pct exec 101 -- ip addr flush dev eth0
      pct stop 101
      vzdump 101 --dumpdir /root/tp --compress zstd
      rm -rf /root/tp/*.log
      backup_file_name=$(ls /root/tp | grep "vzdump")
      real_name=$(echo "${image}" | sed 's/_amd64\..*//')
      mv /root/tp/${backup_file_name} /root/tp/${real_name}_amd64.tar.zst
      rm -rf /root/tp/vzdump*
      pct destroy 101
    done
done
