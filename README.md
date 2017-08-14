# cf-pkgdiff

Outputs a list of differences between two versions of either a stemcell or rootfs
available for Cloud Foundry.

```
usage: pkgdiff.py [-h] (-sa | -sv | -r) VERSION1 VERSION2

Diff the packages between two stemcell versions.

positional arguments:
  VERSION1              antecedent version
  VERSION2              descendent version

optional arguments:
  -h, --help            show this help message and exit
  -sa, --stemcell-aws
  -sg, --stemcell-google
  -sv, --stemcell-vsphere
  -sz, --stemcell-azure
  -r, --rootfs
```
