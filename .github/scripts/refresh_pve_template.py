#!/usr/bin/env python3
"""Publish a freshly verified Proxmox template from its maintained public producer."""
import argparse,base64,datetime,json,os,platform,re,subprocess,sys
from pathlib import Path
from release_assets import Publisher
from verify_template_identity import verify_template_identity


def validate_image(filename):
    environment=os.environ.copy()
    environment.pop('GH_TOKEN',None)
    environment.pop('GITHUB_TOKEN',None)
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


def source_configuration(architecture):
    if architecture=='amd64':
        return 'oneclickvirt/lxc_amd64_images', ('amd64','x86_64')
    if architecture=='arm64':
        return 'oneclickvirt/lxc_arm_images', ('arm64','aarch64')
    raise ValueError('unsupported template architecture')


def select_candidates(assets, releases, distro, variant, architecture):
    _,aliases=source_configuration(architecture)
    allowed={distro+'_'+r['version']+'_'+r['release']+'_'+a+'_'+variant+'.tar.xz'
             for r in releases if r['release'] not in ['forky','snapshot','edge'] for a in aliases}
    pattern=distro+r'_[A-Za-z0-9_.-]+_('+'|'.join(aliases)+')_'+variant+r'\.tar\.xz'
    candidates=[a for a in assets if a['name'] in allowed and a.get('state')=='uploaded' and a.get('size')
                and re.fullmatch(pattern,a['name'])]
    return select_latest(candidates,releases,distro,variant)


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


def publish_outputs(outputs):
    if not outputs:
        raise RuntimeError('No maintained PVE templates passed hosted validation; previous release retained')
    subprocess.run(['python3','.github/scripts/release_assets.py','maintained',*outputs],check=True,timeout=1800)
    print('Published a maintained PVE template; historical assets retained:',len(outputs))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('distro')
    parser.add_argument('--arch',choices=['amd64','arm64'],default='amd64')
    parser.add_argument('--release',help='One maintained catalog release; omitted refreshes all maintained releases')
    args=parser.parse_args()
    if args.distro not in ['almalinux','alpine','archlinux','centos','debian','fedora','gentoo','kali','openeuler','opensuse','openwrt','oracle','rockylinux','ubuntu']:
        raise ValueError('unsupported template distribution')
    native={'x86_64':'amd64','aarch64':'arm64','arm64':'arm64'}.get(platform.machine())
    if native!=args.arch:
        raise RuntimeError('Template validation requires a native '+args.arch+' worker')
    repository,_=source_configuration(args.arch)
    source=Publisher(repository,os.environ['GH_TOKEN'])
    release=source.request(source.base+'/releases/tags/'+args.distro)
    variant='openrc' if args.distro=='gentoo' else 'default'
    catalog_file=source.request(source.base+'/contents/.github/image-catalog.json?ref=main')
    catalog=json.loads(base64.b64decode(catalog_file['content']))
    spec=catalog['distros'][args.distro]
    if args.arch not in spec['architectures']:
        raise ValueError('The maintained source does not support this architecture')
    releases=spec['releases']
    if args.release:
        releases=[r for r in releases if args.release in (r['version'],r['release'])]
        if len(releases)!=1:raise ValueError('Expected one maintained source release')
    candidates=select_candidates(source.assets(release['id']).values(),releases,args.distro,variant,args.arch)
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
            verify_template_identity(filename,architecture=args.arch)
            validate_image(filename)
            stamp=datetime.datetime.fromisoformat(asset['updated_at'].replace('Z','+00:00')).strftime('%Y%m%d')
            stem=filename.name[:-7]
            output=Path(stem+'_'+stamp+'_'+args.arch+'.tar.zst')
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
            verify_template_identity(output,architecture=args.arch)
            validate_image(output)
            keep_output=True
            return output
        finally:
            temporary.unlink(missing_ok=True)
            filename.unlink(missing_ok=True)
            if output is not None and not keep_output:output.unlink(missing_ok=True)

    outputs=process_candidates(sorted(candidates,key=lambda a:a['name']),process)
    print(f'PVE template refresh: {len(outputs)} accepted, {len(candidates)-len(outputs)} deferred')
    publish_outputs(outputs)

if __name__=='__main__':main()
