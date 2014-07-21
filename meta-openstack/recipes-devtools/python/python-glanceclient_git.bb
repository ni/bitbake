DESCRIPTION = "Client library for Glance built on the OpenStack Images API"
HOMEPAGE = "https://github.com/openstack/python-glanceclient"
SECTION = "devel/python"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=34400b68072d710fecd0a2940a0d1658"
DEPENDS += " \
        gmp \
        python-pip \
        python-pbr \
        "

SRCREV = "68c1d1fbc614d11b95f2fd6da26fd669e40f4186"
PV = "0.13.1+git${SRCPV}"
PR = "0"

SRC_URI = "\
	git://github.com/openstack/${BPN}.git;protocol=https \
	file://fix_glanceclient_memory_leak.patch \
	"

S = "${WORKDIR}/git"

inherit setuptools

FILES_${PN} += "${datadir}/${SRCNAME}"

RDEPENDS_${PN} = "gmp \
   python-warlock \
   python-pyopenssl \
   python-prettytable \
   python-setuptools-git \
   python-pbr \
   "

