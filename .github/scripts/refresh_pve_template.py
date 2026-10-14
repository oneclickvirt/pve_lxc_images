#!/usr/bin/env python3
"""Publish a freshly verified Proxmox template from its maintained public producer."""
import argparse,base64,datetime,json,os,re,subprocess,sys
from pathlib import Path
from release_assets import Publisher


def validate_image(filename):
    environment=os.environ.copy()
    environment.pop('GH_TOKEN',None)
    subprocess.run(['python3','.github/scripts/hosted_image_test.py','--file',str(filename),'--runtime','incus'],
                   check=True,timeout=1200,env=environment)


def select_latest(candidates, release_specs, distro, variant):
    """Bound the refresh to one current asset per catalog release.

    Historical assets remain available in GitHub releases and are covered by
    the explicit image test workflow. Refreshing every historical tarball here
    made a single retired rootfs block all current PVE updates.
    """
    selected=[]
    for spec in release_specs:
        prefix=f"{distro}_{spec['version']}_{spec['release']}_"
        matches=[asset for asset in candidates if asset['name'].startswith(prefix)
                 and asset['name'].endswith(f"_{variant}.tar.xz")]
        if matches:
            selected.append(max(matches,key=lambda asset:(asset.get('updated_at',''),asset['name'])))
    return selected


def process_candidates(candidates, process):
    outputs=[]
    for asset in candidates:
        try:
            output=process(asset)
            if output:
                outputs.append(str(output))
        except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as error:
            # One broken upstream release must not prevent other releases from
            # reaching validation and publication.
            print(f'Deferred {asset["name"]}: {type(error).__name__}: {error}',file=sys.stderr)
    return outputs


def main():
    parser=argparse.ArgumentParser();parser.add_argument('distro');args=parser.parse_args()
    if args.distro not in ['almalinux','alpine','archlinux','centos','debian','fedora','gentoo','kali','openeuler','opensuse','openwrt','oracle','rockylinux','ubuntu']:
        raise ValueError('unsupported template distribution')
    source=Publisher('oneclickvirt/lxc_amd64_images',os.environ['GH_TOKEN'])
    release=source.request(source.base+'/releases/tags/'+args.distro)
    variant='openrc' if args.distro=='gentoo' else 'default'
    catalog_file=source.request(source.base+'/contents/.github/image-catalog.json?ref=main')
    catalog=json.loads(base64.b64decode(catalog_file['content']))
    releases=catalog['distros'][args.distro]['releases']
    allowed={args.distro+'_'+r['version']+'_'+r['release']+'_'+a+'_'+variant+'.tar.xz'
             for r in releases if r['release'] not in ['forky','snapshot','edge'] for a in ['amd64','x86_64']}
    candidates=[a for a in source.assets(release['id']).values() if a['name'] in allowed]
    candidates=[a for a in candidates if a.get('state')=='uploaded' and a.get('size') and
                re.fullmatch(args.distro+r'_[A-Za-z0-9_.-]+_(x86_64|amd64)_'+variant+r'\.tar\.xz',a['name'])]
    candidates=select_latest(candidates,releases,args.distro,variant)
    if not candidates:raise RuntimeError('maintained public source template is unavailable')
    def process(asset):
        filename=Path(asset['name']);temporary=filename.with_suffix(filename.suffix+'.partial')
        output=None;keep_output=False
        try:
            subprocess.run(['curl','--fail','--location','--connect-timeout','15','--max-time','900','--retry','3',
                            '--retry-max-time','180','-o',str(temporary),asset['browser_download_url']],check=True,timeout=1200)
            if temporary.stat().st_size!=asset['size']:raise ValueError('source image size mismatch')
            if asset.get('digest') and asset['digest']!='sha256:'+source.digest(temporary):raise ValueError('source image checksum mismatch')
            temporary.rename(filename)
            validate_image(filename)
            stamp=datetime.datetime.fromisoformat(asset['updated_at'].replace('Z','+00:00')).strftime('%Y%m%d')
            stem=filename.name[:-7]
            output=Path(stem+'_'+stamp+'_amd64.tar.zst')
            # Recompression retains the original tar records, owners and attributes.
            with output.open('wb') as stream:
                unpack=subprocess.Popen(['xz','--decompress','--stdout',str(filename)],stdout=subprocess.PIPE)
                compress=subprocess.Popen(['zstd','--threads=0','-10','--stdout'],stdin=unpack.stdout,stdout=stream)
                unpack.stdout.close()
                try:
                    if compress.wait(timeout=600)!=0 or unpack.wait(timeout=60)!=0:raise RuntimeError('template recompression failed')
                finally:
                    if compress.poll() is None:compress.kill();compress.wait()
                    if unpack.poll() is None:unpack.kill();unpack.wait()
            subprocess.run(['zstd','--test',str(output)],check=True,timeout=300)
            validate_image(output)
            keep_output=True
            return output
        finally:
            temporary.unlink(missing_ok=True)
            filename.unlink(missing_ok=True)
            if output is not None and not keep_output:output.unlink(missing_ok=True)

    outputs=process_candidates(sorted(candidates,key=lambda a:a['name']),process)
    if not outputs:
        print('No maintained PVE templates passed hosted validation; previous release retained.',file=sys.stderr)
        return
    subprocess.run(['python3','.github/scripts/release_assets.py','maintained',*outputs],check=True,timeout=1800)
    print('Published a maintained PVE template; historical assets retained:',len(outputs))

if __name__=='__main__':main()
