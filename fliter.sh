#!/bin/bash
# from
# https://github.com/oneclickvirt/pve_lxc_images

url="http://download.proxmox.com/images/system/"
images=()
fixed_images=($(curl -s -H "Accept: application/vnd.github.v3+json" "https://api.github.com/repos/oneclickvirt/pve_lxc_images/releases/tags/images" | grep -oP '"name": "\K[^"]+' | grep -v "images" | awk 'NR%2==1' | sed 's/_amd64\..*//'))
while IFS= read -r line; do
  fixed_image=false
  for fa in "${fixed_images[@]}"; do
    if [[ $line == *"$fa"* ]]; then
        fixed_image=true
        break
    fi
  done
  if [ "$fixed_image" == false ]; then
    if [[ ! $line =~ \.aplinfo && $line != '../' ]]; then
      images+=("$line")
    fi
  fi
done < <(curl -s "$url" | grep -oP '(?<=href=")[^"]+')
length=${#images[@]}
for image in "${images[@]}"; do
  echo "$image"
done
