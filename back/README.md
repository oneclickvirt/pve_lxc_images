## auto

```shell
curl -L https://raw.githubusercontent.com/oneclickvirt/pve_lxc_images/main/build_from_website.sh -o build_from_website.sh && chmod +x build_from_website.sh && ./build_from_website.sh
```

```shell
curl -L https://raw.githubusercontent.com/oneclickvirt/pve_lxc_images/main/build_from_pveam.sh -o build_from_pveam.sh && chmod +x build_from_pveam.sh && ./build_from_pveam.sh
```

```shell
url="http://download.proxmox.com/images/system/"
images=()
while IFS= read -r line; do
  if [[ $line =~ fedora ]]; then
    images+=("$line")
  fi
done < <(curl -s "$url" | grep -oP '(?<=href=")[^"]+')
length=${#images[@]}
for image in "${images[@]}"; do
  echo "$image"
  if [ ! -f "${image}" ];then
      wget "http://download.proxmox.com/images/system/${image}"
  fi
done
```
