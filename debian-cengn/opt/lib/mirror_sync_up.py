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
import git
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


def md5_checksum(dl_file, md5sum, logger):

    if not os.path.exists(dl_file):
        return False

    md5 = run_shell_cmd('md5sum %s |cut -d" " -f1' % dl_file, logger)
    if md5 != md5sum:
        return False
    return True


def parse_url(url):

    url_change = urllib.parse.urlparse(url)
    path = pathlib.Path(url_change.path)
    if url_change.netloc != '':
        local_dir = pathlib.Path(url_change.netloc, path.parent.relative_to("/"))
    else:
        local_dir = path.parent
    local_dir.mkdir(parents=True, exist_ok=True)
    save_file = pathlib.Path(local_dir, path.name)

    return local_dir, save_file


def download(url, md5sum, logger):

    _, save_file = parse_url(url)

    if not md5_checksum(save_file, md5sum, logger):
        logger.info(f"Download {url} to {save_file}")
        download_cmd = "wget -t 5 --wait=15 %s -O %s"
        run_shell_cmd(download_cmd % (url, save_file), logger)
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


def check_dsc(dsc_file, logger):

    logger.info("Check %s" % dsc_file)
    if not os.path.exists(dsc_file):
        return False

    with open(dsc_file) as f:
        c = debian.deb822.Dsc(f)

    base_dir = os.path.dirname(dsc_file)
    for f in c['Files']:
        local_f = os.path.join(base_dir, f['name'])
        if not md5_checksum(local_f, f['md5sum'], logger):
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

    # for repo in repo_list:
    #     repo_url = os.path.join(url_base, repo)
    #     repo_path = os.path.join(repo_base, repo)
    #     if is_git_repo(repo_path):
    #         logger.info('Pulling %s ...', repo)
    #         repo = git.Repo(repo_path)
    #         try:
    #             repo.git.checkout(branch)
    #             repo.git.pull()
    #         except git.exc.GitCommandError:
    #             logging.error('Failed to pull %s', repo)
    #             raise 
    #     else:
    #         logger.info('Cloning %s ...', repo)
    #         try:
    #             repo = git.Repo.clone_from(repo_url, repo_path, single_branch=True, b=branch)
    #         except git.exc.GitCommandError:
    #             logging.error('Failed to clone %s', repo)
    #             raise

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

    yaml_list = []
    # for root, dirs, _ in os.walk(repo_base):
    #    for d in dirs:
    for d in git_list(dir=repo_base):
        if True:
            # debian_pkg_dirs = os.path.join(root, d, "debian_pkg_dirs")
            debian_pkg_dirs = os.path.join(d, "debian_pkg_dirs")
            if not os.path.exists(debian_pkg_dirs):
                continue
            pkg_file = open(debian_pkg_dirs,  "r")
            pkgs = pkg_file.readlines()
            for pkg in pkgs:
                if pkg.strip() == "":
                    continue
                # yaml_file = os.path.join(root, d, pkg.strip(), "debian/meta_data.yaml")
                yaml_file = os.path.join(d, pkg.strip(), "debian/meta_data.yaml")
                if not os.path.exists(yaml_file):
                    continue
                yaml_list.append(yaml_file)

    if not os.path.exists(mirror_base):
        run_shell_cmd("mkdir -p %s" % mirror_base, logger)

    pwd = os.getcwd()
    os.chdir(mirror_base)

    # SAL
    failed_urls = {}
    for yaml_file in yaml_list:
        logger.info("Parse %s", yaml_file)
        try:
            with open(yaml_file) as f:
                meta_data = yaml.full_load(f)
        except IOError:
            logger.error("Can't open '%s'", yaml_file)
            # SAL sys.exit(1)
            failed_yaml_list.append(yaml_file)
            continue

        pkgname = pathlib.Path(yaml_file).parent.parent.name
        if "debname" in meta_data:
            pkgname = meta_data["debname"]
        debver = str(meta_data["debver"]).split(":")[-1]

        # SAL
        if "dl_path" in meta_data:
            try:
                download(meta_data["dl_path"]["url"], meta_data["dl_path"]["md5sum"], logger)
            except Exception:
                logger.error("Failed to download '%s' from '%s'", meta_data["dl_path"]["url"], yaml_file)
                failed_urls[yaml_file] = [ meta_data["dl_path"]["url"] ]
        elif "archive" in meta_data:
            dsc_filename = pkgname + "_" + debver + ".dsc"
            dsc_file = os.path.join(meta_data["archive"], dsc_filename)
            local_dir, _ = parse_url(dsc_file)
            if not check_dsc(os.path.join(local_dir, dsc_filename), logger):
                try:
                    run_shell_cmd("cd %s;dget -d %s" % (local_dir, dsc_file), logger)
                except Exception:
                    logger.error("Failed to download '%s' from '%s'", dsc_file, yaml_file)
                    failed_urls[yaml_file] = [ dsc_file ]
            else:
                logger.info("Already downloaded '%s'" % dsc_file,)

        if "dl_files" in meta_data:
            for dl_file in meta_data['dl_files']:
                url = meta_data['dl_files'][dl_file]['url']
                md5sum = meta_data['dl_files'][dl_file]['md5sum']
                try:
                    download(url, md5sum, logger)
                except Exception:
                    logger.error("Failed to download '%s' from '%s'", url, yaml_file)
                    if yaml_file in failed_urls:
                        failed_urls[yaml_file].append(url)
                    else:
                        failed_urls[yaml_file] = [ url ]

    if len(failed_urls) > 0:
        logger.error("=== List of failed yaml files and urls ===")
        for failed_yaml_file in failed_urls:
            for failed_url in failed_urls[failed_yaml_file]:
               logger.error("%s : %s", failed_yaml_file, failed_url)
        
    os.chdir(pwd)


if __name__ == "__main__":

    main()
