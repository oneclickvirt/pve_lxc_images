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
      pct exec 101 -- ip addr flush dev spiritlhl
      pct stop 101
      vzdump 101 --dumpdir /root/tp --compress zstd
      rm -rf /root/tp/*.log
      backup_file_name=$(ls /root/tp | grep "vzdump")
      real_name=$(echo "${release_name}" | sed 's/_amd64\..*//')
      mv /root/tp/${backup_file_name} /root/tp/${real_name}_amd64.tar.zst
      rm -rf /root/tp/vzdump*
      pct destroy 101
done

# for image in *; do
#       echo "$image"
#       echo "$image" >> log
#       pct create 102 "$image" -cores 6 -cpuunits 1024 -memory 26480 -swap 0 -rootfs local:10 -onboot 1 -features nesting=1
#       pct start 102
#       pct set 102 --hostname 101
#       res0=$(pct set 102 --net0 name=eth0,ip=172.16.1.3/24,bridge=vmbr1,gw=172.16.1.1)
#       if [[ $res0 == *"error"* || $res0 == *"failed: exit code"* ]]; then
#           echo "set eth0 failed" >> log
#       fi
#       pct set 102 --nameserver 1.1.1.1
#       pct set 102 --searchdomain local
#       sleep 5
#       res1=$(pct exec 102 -- lsof -i:22)
#       if [[ $res1 == *"command not found"* ]]; then
#           res1=$(pct exec 102 -- ${manager} install -y lsof)
#       fi
#       sleep 1
#       res1=$(pct exec 102 -- lsof -i:22)
#       if [[ $res1 == *"ssh"* ]]; then
#           echo "ssh config correct"
#       fi
#       res2=$(pct exec 102 -- curl --version)
#       if [[ $res2 == *"command not found"* ]]; then
#           echo "no curl" >> log
#       fi
#       res3=$(pct exec 102 -- wget --version)
#       if [[ $res3 == *"command not found"* ]]; then
#           echo "no wget" >> log
#       fi
#       echo "nameserver 8.8.8.8" | pct exec 102 -- tee -a /etc/resolv.conf
#       res4=$(pct exec 102 -- curl -lk https://raw.githubusercontent.com/spiritLHLS/ecs/main/back/test)
#       if [[ $res4 == *"success"* ]]; then
#           echo "network is public"
#       else
#           echo "no public network" >> log
#       fi
#       pct exec 102 -- reboot
#       sleep 6
#       res5=$(pct exec 102 -- curl -lk https://raw.githubusercontent.com/spiritLHLS/ecs/main/back/test)
#       if [[ $res5 == *"success"* ]]; then
#           echo "reboot success"
#       else
#           echo "reboot failed" >> log
#       fi
#       pct stop 102
#       pct destroy 102
#       echo "------------------------------------------" >> log
#     done
