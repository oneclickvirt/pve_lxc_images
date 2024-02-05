#!/bin/bash
# from
# https://github.com/oneclickvirt/pve_lxc_images

# ./buildct.sh

# 用颜色输出信息
_red() { echo -e "\033[31m\033[01m$@\033[0m"; }
_green() { echo -e "\033[32m\033[01m$@\033[0m"; }
_yellow() { echo -e "\033[33m\033[01m$@\033[0m"; }
_blue() { echo -e "\033[36m\033[01m$@\033[0m"; }
reading() { read -rp "$(_green "$1")" "$2"; }
utf8_locale=$(locale -a 2>/dev/null | grep -i -m 1 -E "UTF-8|utf8")
if [[ -z "$utf8_locale" ]]; then
    echo "No UTF-8 locale found"
else
    export LC_ALL="$utf8_locale"
    export LANG="$utf8_locale"
    export LANGUAGE="$utf8_locale"
    echo "Locale set to $utf8_locale"
fi
# CN=true

get_system_arch() {
    local sysarch="$(uname -m)"
    if [ "${sysarch}" = "unknown" ] || [ "${sysarch}" = "" ]; then
        local sysarch="$(arch)"
    fi
    # 根据架构信息设置系统位数并下载文件,其余 * 包括了 x86_64
    case "${sysarch}" in
    "i386" | "i686" | "x86_64")
        system_arch="x86"
        ;;
    "armv7l" | "armv8" | "armv8l" | "aarch64")
        system_arch="arch"
        ;;
    *)
        system_arch=""
        ;;
    esac
}

get_system_arch
if [ -z "${system_arch}" ] || [ ! -v system_arch ]; then
    _red "This script can only run on machines under x86_64 or arm architecture."
    exit 1
fi
cd /root >/dev/null 2>&1
CTID="${1:-102}"
core="${2:-1}"
memory="${3:-512}"
disk="${4:-5}"
storage="${5:-local}"
url="http://download.proxmox.com/images/system/"
images=()
while IFS= read -r line; do
  if [[ ! $line =~ \.aplinfo && $line != '../' && ! $line =~ opensuse && ! $line =~ gentoo && ! $line =~ alpine && ! $line =~ archlinux && ! $line =~ fedora ]]; then
    images+=("$line")
  fi
done < <(curl -s "$url" | grep -oP '(?<=href=")[^"]+')
length=${#images[@]}
for image in "${images[@]}"; do
  echo "$image"
  curl -o "/var/lib/vz/template/cache/${image}" "http://download.proxmox.com/images/system/${image}"
done

check_cdn() {
    local o_url=$1
    for cdn_url in "${cdn_urls[@]}"; do
        if curl -sL -k "$cdn_url$o_url" --max-time 6 | grep -q "success" >/dev/null 2>&1; then
            export cdn_success_url="$cdn_url"
            return
        fi
        sleep 0.5
    done
    export cdn_success_url=""
}

check_cdn_file() {
    check_cdn "https://raw.githubusercontent.com/spiritLHLS/ecs/main/back/test"
    if [ -n "$cdn_success_url" ]; then
        _yellow "CDN available, using CDN"
    else
        _yellow "No CDN available, no use CDN"
    fi
}

cdn_urls=("https://cdn0.spiritlhl.top/" "http://cdn3.spiritlhl.net/" "http://cdn1.spiritlhl.net/" "https://ghproxy.com/" "http://cdn2.spiritlhl.net/")
check_cdn_file
CTIDs=()
for ((i=0; i<${#images[@]}; i++)); do
    CTID=$((start_value + i))
    CTIDs+=($CTID)
done
for ((i=0; i<${#images[@]}; i++)); do
    CTID=${CTIDs[i]}
    image=${images[i]}
    
    first_digit=${CTID:0:1}
    second_digit=${CTID:1:1}
    third_digit=${CTID:2:1}
    if [ $first_digit -le 2 ]; then
        if [ $second_digit -eq 0 ]; then
            num=$third_digit
        else
            num=$second_digit$third_digit
        fi
    else
        num=$((first_digit - 2))$second_digit$third_digit
    fi
    
    user_ip="172.16.1.${num}"
    pct create $CTID ${storage}:vztmpl/$image -cores $core -cpuunits 1024 -memory $memory -swap 128 -rootfs ${storage}:${disk} -onboot 1 -features nesting=1
    pct start $CTID
    pct set $CTID --hostname $CTID
    pct set $CTID --net0 name=eth0,ip=${user_ip}/24,bridge=vmbr1,gw=172.16.1.1
    pct set $CTID --nameserver 1.1.1.1
    pct set $CTID --searchdomain local
    sleep 3
    if echo "$image" | grep -qiE "centos|almalinux|rockylinux"; then
        pct exec $CTID -- yum install -y curl
        if [[ -z "${CN}" || "${CN}" != true ]]; then
            pct exec $CTID -- yum update -y 
            pct exec $CTID -- yum update
            pct exec $CTID -- yum install -y dos2unix curl
        else
            pct exec $CTID -- yum install -y curl
            pct exec $CTID -- curl -lk https://gitee.com/SuperManito/LinuxMirrors/raw/main/ChangeMirrors.sh -o ChangeMirrors.sh
            pct exec $CTID -- chmod 777 ChangeMirrors.sh
            pct exec $CTID -- ./ChangeMirrors.sh --source mirrors.tuna.tsinghua.edu.cn --web-protocol http --intranet false --close-firewall true --backup true --updata-software false --clean-cache false --ignore-backup-tips
            pct exec $CTID -- rm -rf ChangeMirrors.sh
            pct exec $CTID -- yum install -y dos2unix
        fi
    else
        if [[ -z "${CN}" || "${CN}" != true ]]; then
            pct exec $CTID -- apt-get update -y
            pct exec $CTID -- dpkg --configure -a
            pct exec $CTID -- apt-get update
            pct exec $CTID -- apt-get install dos2unix curl -y
        else
            pct exec $CTID -- apt-get install curl -y --fix-missing
            pct exec $CTID -- curl -lk https://gitee.com/SuperManito/LinuxMirrors/raw/main/ChangeMirrors.sh -o ChangeMirrors.sh
            pct exec $CTID -- chmod 777 ChangeMirrors.sh
            pct exec $CTID -- ./ChangeMirrors.sh --source mirrors.tuna.tsinghua.edu.cn --web-protocol http --intranet false --close-firewall true --backup true --updata-software false --clean-cache false --ignore-backup-tips
            pct exec $CTID -- rm -rf ChangeMirrors.sh
            pct exec $CTID -- apt-get install dos2unix -y
        fi
    fi
    pct exec $CTID -- curl -L ${cdn_success_url}https://raw.githubusercontent.com/spiritLHLS/pve/main/scripts/ssh.sh -o ssh.sh
    pct exec $CTID -- chmod 777 ssh.sh
    pct exec $CTID -- dos2unix ssh.sh
    pct exec $CTID -- bash ssh.sh
    # 禁止PVE自动修改网络接口设置
    pct exec $CTID -- touch /etc/network/.pve-ignore.interfaces
    # 禁止PVE自动修改DNS设置
    pct exec $CTID -- touch /etc/.pve-ignore.resolv.conf
    # 禁止PVE自动修改主机名设置
    pct exec $CTID -- touch /etc/.pve-ignore.hosts
    pct exec $CTID -- touch /etc/.pve-ignore.hostname
    # 删除缓存，删除备份前需要删除的内容
    pct exec $CTID -- apt-get clean
    pct exec $CTID -- apt-get autoclean
    pct exec $CTID -- apt-get autoremove
    pct exec $CTID -- rm /etc/resolv.conf
    pct exec $CTID -- rm /etc/hostname
done
