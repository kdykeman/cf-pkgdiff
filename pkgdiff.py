#!/usr/bin/env python

import sys
import os.path
import logging
import argparse
import tempfile
import urllib2
import tarfile
import shutil

logging.basicConfig(stream=sys.stdout, level=logging.ERROR)
log = logging.getLogger("scdiff.py")

class Package:
   def __init__(self, pkgtype, version):
      self.pkgtype = pkgtype
      self.version = version
      self.tmpdir = tempfile.mkdtemp(prefix='scdiff_', dir=None)

      if pkgtype is 'rootfs':
         self.filename = "%s.tar.gz" % self.version
         self.url = "https://github.com/cloudfoundry/stacks/archive/%s" % self.filename
         self.pkglist_filename = os.path.join(self.tmpdir, "stacks-"+self.version, "cflinuxfs2", "cflinuxfs2_receipt")
      elif pkgtype is 'stemcell_aws':
         self.filename = "light-bosh-stemcell-%s-aws-xen-hvm-ubuntu-trusty-go_agent.tgz" % self.version
         if float(version) < 3300:
             self.url = "https://d26ekeud912fhb.cloudfront.net/bosh-stemcell/aws/%s" % self.filename
         else:
             self.url = "https://s3.amazonaws.com/bosh-aws-light-stemcells/%s" % self.filename
         self.pkglist_filename = os.path.join(self.tmpdir, "stemcell_dpkg_l.txt")
      elif pkgtype is 'stemcell_vsphere':
         self.filename = "bosh-stemcell-%s-vsphere-esxi-ubuntu-trusty-go_agent.tgz" % self.version
         if float(version) < 3300:
             self.url = "https://d26ekeud912fhb.cloudfront.net/bosh-stemcell/vsphere/%s" % self.filename
         else:
             self.url = "https://s3.amazonaws.com/bosh-core-stemcells/vsphere/%s" % self.filename
         self.pkglist_filename = os.path.join(self.tmpdir, "stemcell_dpkg_l.txt")
      elif pkgtype is 'stemcell_google':
         self.filename = "bosh-stemcell-%s-google-kvm-ubuntu-trusty-go_agent.tgz" % self.version
         self.url = "https://s3.amazonaws.com/bosh-core-stemcells/google/%s" % self.filename
         self.pkglist_filename = os.path.join(self.tmpdir, "stemcell_dpkg_l.txt")
      elif pkgtype is 'stemcell_azure':
         self.filename = "bosh-stemcell-%s-azure-hyperv-ubuntu-trusty-go_agent.tgz" % self.version
         self.url = "https://s3.amazonaws.com/bosh-core-stemcells/azure/%s" % self.filename
         self.pkglist_filename = os.path.join(self.tmpdir, "stemcell_dpkg_l.txt")
      else:
         log.error("Unsupported package type: %s" % pkgtype)
         raise ValueError("Unsupported package type: %s" % pkgtype)


def fetch_url(url, dirpath):
    """Downloads the specified url to the specified directory."""

    file_name = url.split('/')[-1]
    u = urllib2.urlopen(url)
    f = open(os.path.join(dirpath, file_name), 'wb')
    meta = u.info()
    log.debug("meta: %s" % meta)
    file_size=''
    if meta.getheaders("Content-Length"):
        file_size = int(meta.getheaders("Content-Length")[0])
    print "Downloading: %s Bytes: %s" % (file_name, file_size)

    file_size_dl = 0
    block_sz = 8192
    while True:
        buffer = u.read(block_sz)
        if not buffer:
            break

        file_size_dl += len(buffer)
        f.write(buffer)
        if file_size:
            status = r"%10d  [%3.2f%%]" % (file_size_dl, file_size_dl * 100. / file_size)
        else:
            status = r"%10d  [????]" % (file_size_dl)

        status = status + chr(8)*(len(status)+1)
        print status,
    f.close()


def unpack(dirpath, filename):
    """Unpacks a tarball with a given filename"""

    filepath = os.path.join(dirpath, filename)
    if not os.path.isfile(filepath):
        raise FileNotFoundError("File not found: %s" % filepath)
    elif not os.access(filepath, os.R_OK):
        raise PermissionError("Cannot read: %s" % filepath)

    log.debug("unpack: %s" % filepath)
    tar = tarfile.open(name=filepath, mode='r')
    tar.extractall(path=dirpath)
    tar.close()


def get_pkghash(target):
    """Gets a dictionary of package, version for the specified target"""
    pkghash = {}

    fetch_url(target.url, target.tmpdir)
    unpack(target.tmpdir, target.filename)

    pkglist_file = open(target.pkglist_filename, "r")
    for line in pkglist_file:
        words = line.split()
        if not len(words) > 3:
            continue
        pkghash[words[1]] = words[2]
    pkglist_file.close()

    shutil.rmtree(target.tmpdir, ignore_errors=True)
    return pkghash


def get_pkglist_changes(target1, target2):
    """Get a list of package list changes between two targets"""

    print "target1 url: %s" % target1.url
    print "target2 url: %s" % target2.url

    pkghash1 = get_pkghash(target1)
    pkghash2 = get_pkghash(target2)

    changehash = {}
    for pkgname1, version1 in pkghash1.items():
        # add versions
        log.debug("%s-%s" % (pkgname1, version1))
        if pkgname1 not in pkghash2:
            log.debug("pkg only in antecedent")
            changehash[pkgname1] = (version1, '')
        else:
            version2 = pkghash2[pkgname1]
            if not version1 == version2:
                log.debug("versions differ: %s, %s" % (version1, version2))
                changehash[pkgname1] = (version1, version2)

    for pkgname2, version2 in pkghash2.items():
        if not pkgname2 in pkghash1:
            changehash[pkgname2] = ('', version2)
            log.debug("pkg only in suffix %s" % pkgname2)

    log.debug(changehash)

    return changehash


def main(argv):

  parser = argparse.ArgumentParser(description='Diff the packages between two stemcell versions.')
  parser.add_argument('version1', metavar='VERSION1', nargs=1,
                    help='antecedent version')

  parser.add_argument('version2', metavar='VERSION2', nargs=1,
                    help='descendent version')

  group = parser.add_mutually_exclusive_group(required=True)
  group.add_argument("-sa", "--stemcell-aws", action="store_true")
  group.add_argument("-sz", "--stemcell-azure", action="store_true")
  group.add_argument("-sg", "--stemcell-google", action="store_true")
  group.add_argument("-sv", "--stemcell-vsphere", action="store_true")
  group.add_argument("-r", "--rootfs", action="store_true")

  args = parser.parse_args()
  log.debug(args)

  package_type=''
  if args.stemcell_aws:
      package_type = 'stemcell_aws'
  elif args.stemcell_azure:
      package_type = 'stemcell_azure'
  elif args.stemcell_google:
      package_type = 'stemcell_google'
  elif args.stemcell_vsphere:
      package_type = 'stemcell_vsphere'
  elif args.rootfs:
      package_type = 'rootfs'

  log.debug("package type: %s" % package_type)

  target1 = Package(package_type, args.version1[0])
  target2 = Package(package_type, args.version2[0])

  changes = get_pkglist_changes(target1, target2)
  print
  print
  print "pkgname, %s, %s" % (target1.version, target2.version)
  for change in sorted(changes):
      print "%s, %s, %s" % (change, changes[change][0], changes[change][1])


if __name__ == "__main__":
   main(sys.argv[1:])
