#!/usr/bin/python3

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Copyright (C) 2021 WindRiver Corporation

import debian.deb822
import fnmatch
import git
import glob
import hashlib
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import urllib.parse
import yaml
from repo_utils import repo_init, repo_sync
from shell_commands import run_shell_cmd
from git_utils import git_list


REPOES_MIRROR = "/inputs/repoes_mirror.yaml"


def get_binary_lists(repo_dir):

    """
    Return all binary packages listed in base-bullseye.lst, os-std.lst,os-rt.lst
    """
    binary_lists = []
    stx_config = os.path.join(repo_dir, 'stx-tools/debian-mirror-tools/config/debian')
    patterns=['base-*.lst', 'os-std.lst', 'os-rt.std']
    for root, dirs, files in os.walk(stx_config):
        for pattern in patterns:
            for f in fnmatch.filter(files, pattern):
                binary_lists.append(os.path.join(root, f))

    return binary_lists

def get_binary_urls(bin_list):
    pkg_list = dict()
    with open(bin_list) as flist:
        lines = list(line for line in (lpkg.strip() for lpkg in flist) if line)
        for pkg in lines:
            pkg = pkg.strip()
            if pkg.startswith('#'):
                continue
            pkg_metadata = pkg.split()
            if len(pkg_metadata) < 3:
                continue
            pkg_name = pkg_metadata[0]
            pkg_url = pkg_metadata[2]
            pkg_list[pkg_name] = pkg_url

    return pkg_list


def checksum(dl_file, checksum, cmd, logger):

    if not os.path.exists(dl_file):
        return False

    if cmd == None:
        return True

    check_sum = run_shell_cmd('%s "%s" |cut -d" " -f1' % (cmd, dl_file), logger)
    if check_sum != checksum:
        logger.debug(f"{cmd} checksum mismatch of {dl_file}")
        return False
    return True


def parse_url(url):

    url_change = urllib.parse.urlparse(url)
    path = pathlib.Path(urllib.parse.unquote(url_change.path))
    if url_change.netloc != '':
        local_dir = pathlib.Path(url_change.netloc, path.parent.relative_to("/"))
    else:
        local_dir = path.parent
    local_dir.mkdir(parents=True, exist_ok=True)
    save_file = pathlib.Path(local_dir, path.name)

    return local_dir, save_file



def download(url, check_sum, check_cmd, logger):

    _, save_file = parse_url(url)

    if not checksum(save_file, check_sum, check_cmd, logger):
        logger.info(f"Download {url} to {save_file}")
        tmp_file = ".".join([str(save_file), "tmp"])
        download_cmd = "rm -rf '%s'; curl -kfL '%s' -o '%s'" % (tmp_file, url, tmp_file)
        run_shell_cmd(download_cmd, logger)
        if not checksum(tmp_file, check_sum, check_cmd, logger):
            raise Exception('checksum mismatch after downloading "%s"' % url)
        run_shell_cmd("mv '%s' '%s'" % (tmp_file, save_file), logger)
    else:
        logger.info("Already downloaded '%s'" % save_file)

    return True


def is_git_repo(path):

    if not os.path.exists(path):
        return False
    try:
        _ = git.Repo(path).git_dir
        return True
    except git.exc.InvalidGitRepositoryError:
        shutil.rmtree(path)
        return False


def checksum_dsc(dsc_file, logger):

    logger.info("validating %s" % dsc_file)
    if not os.path.exists(dsc_file):
        return False

    with open(dsc_file) as f:
        c = debian.deb822.Dsc(f)

    base_dir = os.path.dirname(dsc_file)
    for f in c['Checksums-Sha256']:
        local_f = os.path.join(base_dir, f['name'])
        if not checksum(local_f, f['sha256'], "sha256sum", logger):
            return False

    return True


def clone_repoes(meta_data, logger):

    manifest_url = meta_data["MANIFEST_URL"]
    manifest_revision = meta_data["MANIFEST_REVISION"]
    manifest_file = meta_data["MANIFEST_FILE"]

    repo_base = meta_data["REPO_BASE"]
    # mirror_base = meta_data["MIRROR_BASE"]
    # url_base = meta_data["URL_BASE"]
    # branch = meta_data["BRANCH"]
    # repo_list = meta_data["REPO_LIST"]

    if not os.path.exists(repo_base):
        run_shell_cmd("mkdir -p %s" % repo_base, logger)

    repo_init(dir=repo_base, manifest_url=manifest_url, revision=manifest_revision, manifest=manifest_file, logger=logger)

    repo_sync(dir=repo_base, num_threads=20, logger=logger)

def set_logger():

    logger = logging.getLogger("mirror")
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    return logger



def main():

    logger = set_logger()
   
    try:
        with open(REPOES_MIRROR) as f:
            meta_data = yaml.full_load(f)
    except IOError:
        logger.error("Can't open %s", REPOES_MIRROR)
        sys.exit(1)

    repo_base = meta_data["REPO_BASE"]
    mirror_base = meta_data["MIRROR_BASE"]
    clone_repoes(meta_data, logger)

    # Scan StarlingX git repos, build up a list of meta_data.yaml
    # files for all debian packages we need to build.
    yaml_list = []
    for d in git_list(dir=repo_base):
        if True:
            # debian_pkg_dirs = os.path.join(d, "debian_pkg_dirs")
            for debian_pkg_dirs in glob.glob(os.path.join(d, "debian_pkg_dirs*")):
                if not os.path.exists(debian_pkg_dirs):
                    continue
                pkg_file = open(debian_pkg_dirs,  "r")
                pkgs = pkg_file.readlines()
                for pkg in pkgs:
                    if pkg.strip() == "":
                        continue
                    yaml_file = os.path.join(d, pkg.strip(), "debian/meta_data.yaml")
                    if not os.path.exists(yaml_file):
                        continue
                    yaml_list.append(yaml_file)

    if not os.path.exists(mirror_base):
        run_shell_cmd("mkdir -p %s" % mirror_base, logger)

    pwd = os.getcwd()
    os.chdir(mirror_base)

    # For each meta_data.yaml file, make sure we have a mirror copy
    # of all needed input files for building the package.
    failed_urls = {}
    for yaml_file in yaml_list:
        logger.info("Parse %s", yaml_file)
        try:
            with open(yaml_file) as f:
                meta_data = yaml.full_load(f)
        except IOError:
            logger.error("Can't open '%s'", yaml_file)
            failed_yaml_list.append(yaml_file)
            continue

        pkgname = pathlib.Path(yaml_file).parent.parent.name
        if "debname" in meta_data:
            pkgname = meta_data["debname"]
        debver = str(meta_data["debver"]).split(":")[-1]

        if "dl_path" in meta_data:
            url = meta_data["dl_path"]["url"]
            if "sha256sum" in meta_data["dl_path"]:
                check_cmd = "sha256sum"
                check_sum = meta_data["dl_path"]['sha256sum']
            else:
                logger.warning(f"dl_path missing sha256sum")
                check_cmd = "md5sum"
                check_sum = meta_data["dl_path"]["md5sum"]
            try:
                download(url, check_sum, check_cmd, logger)
            except Exception:
                logger.error("Failed to download '%s' from '%s'", url, yaml_file)
                failed_urls[yaml_file] = [ url ]
        elif "archive" in meta_data:
            dsc_filename = pkgname + "_" + debver + ".dsc"
            dsc_file = os.path.join(meta_data["archive"], dsc_filename)
            local_dir, _ = parse_url(dsc_file)
            if not checksum_dsc(os.path.join(local_dir, dsc_filename), logger):
                try:
                    run_shell_cmd("cd %s;dget -d %s" % (local_dir, dsc_file), logger)
                except Exception:
                    logger.error("Failed to download '%s' from '%s'", dsc_file, yaml_file)
                    failed_urls[yaml_file] = [ dsc_file ]
            else:
                logger.info("Already downloaded '%s'" % dsc_file)

        if "dl_files" in meta_data:
            for dl_file in meta_data['dl_files']:
                dl_file_info = meta_data['dl_files'][dl_file]
                url = dl_file_info['url']
                if "sha256sum" in dl_file_info:
                    check_cmd = "sha256sum"
                    check_sum = dl_file_info['sha256sum']
                else:
                    logger.warning(f"{dl_file} missing sha256sum")
                    check_cmd = "md5sum"
                    check_sum = dl_file_info['md5sum']
                try:
                    download(url, check_sum, check_cmd, logger)
                except Exception as e:
                    logger.error("Failed to download '%s' from '%s'", url, yaml_file)
                    print(e)
                    if yaml_file in failed_urls:
                        failed_urls[yaml_file].append(url)
                    else:
                        failed_urls[yaml_file] = [ url ]

    bin_lists = get_binary_lists(repo_base)
    for bin_list in bin_lists:
        pkgs = get_binary_urls(bin_list)
        for pkg in pkgs:
            try:
                download(pkgs[pkg], None, None, logger)
            except Exception as e:
                logger.error("Failed to download '%s' from '%s'", pkgs[pkg], bin_list)
                print(e)
                if bin_list in failed_urls:
                    failed_urls[bin_list].append(url)
                else:
                    failed_urls[bin_list] = [ url ]

    if len(failed_urls) > 0:
        logger.error("=== List of failed yaml files and urls ===")
        for failed_yaml_file in failed_urls:
            for failed_url in failed_urls[failed_yaml_file]:
               logger.error("%s : %s", failed_yaml_file, failed_url)
    else:
        logger.info("All files downloaded successfully")
        
    os.chdir(pwd)


if __name__ == "__main__":

    main()
