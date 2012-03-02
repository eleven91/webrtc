#!/usr/bin/env python
# Copyright (c) 2012 The WebRTC project authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style license
# that can be found in the LICENSE file in the root of the source
# tree. An additional intellectual property rights grant can be found
# in the file PATENTS.  All contributing project authors may
# be found in the AUTHORS file in the root of the source tree.

__author__ = 'kjellander@webrtc.org (Henrik Kjellander)'

"""Downloads WebRTC resources files from a remote host."""

from optparse import OptionParser
from urlparse import urljoin
import os
import shutil
import sys
import tarfile
import tempfile
import urllib2

DEPS_KEY = 'webrtc_resources_revision'
REMOTE_URL_BASE = 'http://commondatastorage.googleapis.com/webrtc-resources'
VERSION_FILENAME = 'webrtc-resources-version'
FILENAME_PREFIX = 'webrtc-resources-'
EXTENSION = '.tgz'


def main():
  """
  Downloads WebRTC resources files from a remote host.

  This script will download WebRTC resource files used for testing, like audio
  and video files. It will check the current version in the DEPS file and
  compare it with the one downloaded (kept in a text file in the download dir).
  If the DEPS version is different than the one downloaded, the correct version
  will be downloaded.
  """

  # Make it possible to skip download using an environment variable:
  if os.getenv('WEBRTC_SKIP_RESOURCES_DOWNLOAD'):
    print 'Skipping resources download since WEBRTC_SKIP_RESOURCES_DOWNLOAD set'
    return

  project_root_dir = os.path.normpath(sys.path[0] + '/../../')
  deps_file = os.path.join(project_root_dir, 'DEPS')
  downloads_dir = os.path.join(project_root_dir, 'resources')
  current_version_file = os.path.join(downloads_dir, VERSION_FILENAME)

  # Ensure the downloads dir is created.
  if not os.path.isdir(downloads_dir):
    os.mkdir(downloads_dir)

  # Define and parse arguments.
  parser = OptionParser()
  parser.add_option('-f', '--force', action='store_true', dest='force',
                    help='forces download and removal of existing resources.')
  parser.add_option('-b', '--base_url', dest='base_url',
                    help= 'Overrides the default Base URL (%s) and uses the '
                    'supplied URL instead.' % REMOTE_URL_BASE)
  (options, unused_args) = parser.parse_args()

  # Download archive if forced or DEPS version is different than our current.
  current_version = _get_current_version(current_version_file)
  desired_version = _get_desired_version(deps_file)
  if desired_version != current_version or options.force:
    base_url = options.base_url or REMOTE_URL_BASE
    _perform_download(base_url, desired_version, downloads_dir)
  else:
    print 'Already have correct version: %s' % current_version


def _get_current_version(current_version_file):
  """Returns the version already downloaded (if any).

  Args:
      current_version_file: The filename of the text file containing the
          currently downloaded version (if any) on local disk.
  Returns:
      The version number, or 0 if no downloaded version exists.
  """
  current_version = 0
  if os.path.isfile(current_version_file):
    f = open(current_version_file)
    current_version = int(f.read())
    f.close()
    print 'Found downloaded resources: version: %s' % current_version
  return current_version


def _get_desired_version(deps_file):
  """Evaluates the project's DEPS and returns the desired resources version.

  Args:
      deps_file: Full path to the DEPS file of the project.
  Returns:
      The desired resources version.
  """
  # Evaluate the DEPS file as Python code to extract the variables defined.
  locals_dict = {'Var': lambda name: locals_dict['vars'][name],
           'File': lambda name: name,
           'From': lambda deps, definition: deps}
  execfile(deps_file, {}, locals_dict)
  deps_vars = locals_dict['vars']

  desired_version = int(deps_vars[DEPS_KEY])
  print 'Version in DEPS file: %d' % desired_version
  return desired_version


def _perform_download(base_url, desired_version, downloads_dir):
  """Performs the download and extracts the downloaded resources.

  Args:
      base_url: URL that holds the resource downloads.
      desired_version: Desired version, which decides the filename.
  """
  temp_dir = tempfile.mkdtemp(prefix='webrtc-resources-')
  try:
    archive_name = '%s%s%s' % (FILENAME_PREFIX, desired_version, EXTENSION)
    # urljoin requires base URL to end with slash to construct a proper URL
    # to our file:
    if not base_url[-1:] == '/':
      base_url += '/'
    remote_archive_url = urljoin(base_url, archive_name)
    # Download into the temporary directory with display of progress, inspired
    # by the Stack Overflow post at
    # http://stackoverflow.com/questions/2028517/python-urllib2-progress-hook
    temp_filename = os.path.join(temp_dir, archive_name)
    print 'Downloading: %s' % remote_archive_url

    response = urllib2.urlopen(remote_archive_url)
    temp_file = open(temp_filename, 'wb')
    _read_chunks(temp_file, response)
    temp_file.close()

    # Clean up the existing resources dir.
    print 'Removing old resources in %s' % downloads_dir
    shutil.rmtree(downloads_dir)
    os.mkdir(downloads_dir)

    # Extract the archive.
    archive = tarfile.open(temp_filename, 'r:gz')
    archive.extractall(downloads_dir)
    archive.close()
    print 'Extracted resource files into %s' % downloads_dir

    # Write the downloaded version to a text file in the resources dir to avoid
    # re-download of the same version in the future.
    new_version_file = os.path.join(downloads_dir, VERSION_FILENAME)
    f = open(new_version_file, 'w')
    f.write('%d' % desired_version)
    f.close()

  finally:
    # Clean up the temp dir.
    shutil.rmtree(temp_dir)


def _print_progress(bytes_so_far, total_size):
  """Prints a chunk report of the download progress so far.

  Args:
    bytes_so_far: The number of bytes read so far.
    total_size: Total file size of download.
  """
  percent = (float(bytes_so_far) / total_size) * 100
  percent = round(percent, 2)
  sys.stdout.write('Downloaded %d of %d kB (%0.2f%%)\r' %
                   (bytes_so_far/1024, total_size/1024, percent))
  if bytes_so_far >= total_size:
    sys.stdout.write('\n')


def _read_chunks(output_file, response, chunk_size=10*1024):
  """Reads data chunks from the response until we're done downloading.

  Args:
    output_file: The file to write the data into.
    response: The HTTP response to read data from.
    chunk_size: How much to read between each UI update.
  Returns:
    The total number of bytes read."""
  total_size = response.info().getheader('Content-Length').strip()
  total_size = int(total_size)
  bytes_so_far = 0
  while True:
    chunk = response.read(chunk_size)
    output_file.write(chunk)
    bytes_so_far += len(chunk)
    if not chunk:
      break
    _print_progress(bytes_so_far, total_size)
  return bytes_so_far


if __name__ == '__main__':
  main()
