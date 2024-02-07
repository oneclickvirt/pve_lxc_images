#!/bin/bash

release_name="ubuntu"
manager="apt-get"
response=$(curl -s -H "Accept: application/vnd.github.v3+json" "https://api.github.com/repos/oneclickvirt/pve_lxc_images/releases/tags/$release_name")
echo "$response" | jq -r '.assets[].browser_download_url' | while read -r url; do
    filename=$(basename "$url")
    echo "Downloading $filename"
    curl -LO "$url"
done
images=($(echo "$response" | jq -r '.assets[].name'))
for image in "${images[@]}"; do
  echo "$image"
  pct create 102 "$image" -cores 6 -cpuunits 1024 -memory 26480 -swap 0 -rootfs local:10 -onboot 1 -features nesting=1
  pct start 102
  pct set 102 --hostname 101
  res0=$(pct set 102 --net0 name=eth0,ip=172.16.1.3/24,bridge=vmbr1,gw=172.16.1.1)
  if [[ $res0 == *"error"* ]]; then
      echo "$image set eth0 failed" >> log
  fi
  pct set 102 --nameserver 1.1.1.1
  pct set 102 --searchdomain local
  sleep 5
  res1=$(pct exec 102 -- lsof -i:22)
  if [[ $res1 == *"command not found"* ]]; then
      res1=$(pct exec 102 -- ${manager} install -y lsof)
  else
      echo "$image no lsof" >> log
  fi
  sleep 1
  res1=$(pct exec 102 -- lsof -i:22)
  if [[ $res1 == *"ssh"* ]]; then
      echo "ssh config correct"
  else
      echo "$image no ssh" >> log
  fi
  res2=$(pct exec 102 -- curl --version)
  if [[ $res2 == *"command not found"* ]]; then
      echo "$image no curl" >> log
  fi
  res3=$(pct exec 102 -- wget --version)
  if [[ $res3 == *"command not found"* ]]; then
      echo "$image no wget" >> log
  fi
  echo "nameserver 8.8.8.8" | pct exec 102 -- tee -a /etc/resolv.conf
  res4=$(pct exec 102 -- curl -lk https://raw.githubusercontent.com/spiritLHLS/ecs/main/back/test)
  if [[ $res4 == *"success"* ]]; then
      echo "network is public"
  else
      echo "$image no network" >> log
  fi
  pct stop 102
  pct destroy 102
done


