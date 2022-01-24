# Copyright (c) 2021 Wind River Systems, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import fnmatch
import os
from shell_commands import run_shell_cmd


# repo_root [<dir>]:
#      Return the root directory of a repo.
#      Assumes that the given directory lies somewhare
#      within the repo.
#      Note: symlinks are fully expanded.
#

def repo_root (dir=os.getcwd()):
    if dir is None:
        return None
    if not os.path.isdir(dir):
        # Perhaps a file, try the parent directory of the file.
        dir = os.path.dirname(dir)
    if not os.path.isdir(dir):
        return None
    while dir != "/":
        if os.path.isdir(os.path.join(dir, ".repo")):
            return os.path.normpath(dir)
        dir = os.path.dirname(dir)
    return None


def repo_init ( dir=os.getcwd(), manifest_url='https://opendev.org/starlingx/manifest', revision='master', manifest='default.xml', logger=None):
    if dir is None:
        logger.error("repo_init: directory not given")
        return False
    if not os.path.isdir(dir):
        logger.error("repo_init: Directory not found: %s" % dir)
        return False
    
    cmd = "cd %s; repo init -u %s -b %s -m %s" % (dir, manifest_url, revision, manifest)
    try:
        run_shell_cmd(cmd, logger)
    except Exception:
        logger.error("Failed to init repo: %s" % cmd)
        return False
    return True


def repo_sync ( dir=os.getcwd(), force=False, delete=False, num_threads=1, logger=None ):
    if dir is None:
        logger.error("repo_sync: directory not given")
        return False
    if not os.path.isdir(dir):
        logger.error("repo_sync: Directory not found: %s" % dir)
        return False

    cmd = "cd %s; repo sync" % dir
    if force:
        cmd += " --force-sync"
    if delete:
        cmd += " -d"
    if num_threads != 1:
        cmd += " -j%d" % num_threads
    try:
        run_shell_cmd(cmd, logger)
    except Exception:
        logger.error("Failed to init repo: %s" % cmd)
        return False
    return True
