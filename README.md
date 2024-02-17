# pve_lxc_images

不支持：devuan、gentoo、archlinux

部分支持：fedora

完全支持：ubuntu、debian、centos、almalinux、rockylinux、alpine、opensuse

## 说明

已预安装：openssh、lsof、curl、wget、sudo、nano、sshpass

已替换可使用的源，均为可使用的源，且均已更新过源

已预设置开机自启SSH，预设置支持IPV4和IPV6的22端口进行SSH链接，预设置支持root登录

未设置默认密码，未设置DNS，未设置网关

部分旧镜像有对应的缺陷，详见仓库对应release的说明

## 手动修补的部分命令

```shell
image=""
pct create 101 "$image" -cores 1 -cpuunits 1024 -memory 1024 -swap 0 -rootfs local:10 -onboot 1 -features nesting=1
pct start 101
pct set 101 --hostname 101
pct set 101 --net0 name=eth0,ip=172.16.1.2/24,bridge=vmbr1,gw=172.16.1.1
pct set 101 --nameserver 1.1.1.1
pct set 101 --searchdomain local
sleep 3
echo "nameserver 8.8.8.8" | pct exec $CTID -- tee -a /etc/resolv.conf
echo "nameserver 8.8.4.4" | pct exec $CTID -- tee -a /etc/resolv.conf
```

```shell
pct enter 101
```

```shell
# https://raw.githubusercontent.com/SuperManito/LinuxMirrors/main/ChangeMirrors.sh
./ChangeMirrors.sh --use-official-source --web-protocol http --intranet false --close-firewall true --backup true --updata-software false --clean-cache false --ignore-backup-tips
```

```shell
# https://raw.githubusercontent.com/SuperManito/LinuxMirrors/main/ChangeMirrors.sh
./ChangeMirrors.sh --use-official-source --web-protocol http --intranet false --close-firewall true --backup true --updata-software false --clean-cache false --install-epel true --ignore-backup-tips
```

https://help.mirrors.cernet.edu.cn/

```shell
# https://raw.githubusercontent.com/oneclickvirt/pve_lxc_images/main/ssh_bash.sh
chmod 777 ssh_bash.sh
./ssh_bash.sh
```

```shell
# https://raw.githubusercontent.com/oneclickvirt/pve_lxc_images/main/ssh_sh.sh
chmod 777 ssh_sh.sh
./ssh_sh.sh
```

```shell
pct exec 101 -- yum clean all -y
pct exec 101 -- yum autoremove -y
```

```shell
pct exec 101 -- apt-get clean
pct exec 101 -- apt-get autoclean
pct exec 101 -- apt-get autoremove
```

```shell
pct exec 101 -- touch /etc/network/.pve-ignore.interfaces
pct exec 101 -- touch /etc/.pve-ignore.resolv.conf
pct exec 101 -- touch /etc/.pve-ignore.hosts
pct exec 101 -- touch /etc/.pve-ignore.hostname
pct exec 101 -- rm -rf /etc/resolv.conf
pct exec 101 -- rm -rf /etc/hostname
pct exec 101 -- rm -rf /etc/network/interfaces
pct exec 101 -- ip addr flush dev eth0
pct set 101 --delete net0
pct stop 101
echo "$image"
```

```shell
vzdump 101 --dumpdir /root/tp --compress zstd
rm -rf /root/tp/*.log
backup_file_name=$(ls /root/tp | grep "vzdump")
real_name=$(echo "${image}" | sed 's/_amd64\..*//')
mv /root/tp/${backup_file_name} /root/tp/${real_name}_amd64.tar.zst
rm -rf /root/tp/vzdump*
pct destroy 101
```

## 上传到对应release

```
# https://api.github.com/repos/oneclickvirt/pve_lxc_images/releases/tags/images
release_id="139874716"
token=""
for file in *; do
    if [ -f "$file" ]; then
        echo "Uploading $file..."
        curl -s -H "Authorization: Bearer $token" \
             -H "Content-Type: application/zip" \
             --data-binary @"$file" \
             "https://uploads.github.com/repos/oneclickvirt/pve_lxc_images/releases/$release_id/assets?name=$(basename "$file")"
        rm -rf $file
        echo ""
    fi
done
```

## Thanks 

http://download.proxmox.com/images/system/

https://github.com/spiritLHLS/pve


