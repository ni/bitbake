"""
BitBake 'Fetch' implementation for NI Artifactory

Class for fetching files via NI Artifactory. It uses wget to perform the download.
The format for the SRC_URI is mostly similar to the one specified in NIBuild's package file.
See example below for details.

Requires the environment variable NIARTIFACTS_TOKEN.

Example:
    NIBuild package:
        perforcePath = artifact://provider/component/channel/export/25.5.0/25.5.0f0;
    SRC_URI:
        SRC_URI = "niartifact://provider/component/channel/export/25.5.0/25.5.0f0/export.zip"
"""

# Copyright (C) 2025  National Instruments Corporation
#
# Based in part on bb.fetch2.wget:
#    Copyright (C) 2003, 2004  Chris Larson
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Based on functions from the base bb module, Copyright 2003 Holger Schurig

import re
import urllib.error
import urllib.request

from bb.fetch2 import check_network_access, FetchError, FetchMethod, runfetchcmd
from bb.utils import mkdirhier


_NIARTIFACT_URI_PATTERN = re.compile(
    r"""
 \s*                                    # Skip leading whitespace
 niartifact://                          # scheme
 (?P<provider>[^/]+)                    # provider name
 /
 (?P<component>[^/]+)                   # component name
 /
 (?P<channel>[^/]+)                     # channel name
 /export/
 (?P<base_version>[^/]+)                # base version
 /
 (?P<version>[^/]+)                     # version
 /
 (?P<filename>[^/]+)                    # filename
 (?P<params>(;[^;]+)*)?                 # parameters block (optional)
 $
""",
    re.VERBOSE,
)


def _parse_niartifact_uri(uri: str) -> dict:
    """Parse the niartifact URI and return its components."""
    match = _NIARTIFACT_URI_PATTERN.match(uri)
    if not match:
        raise FetchError(f"Invalid niartifact URI: {uri}")

    raw_channel = match.group("channel")
    channel = "ci" if raw_channel == "official" else "proto"

    provider = match.group("provider")
    component = match.group("component")
    base_version = match.group("base_version")
    version = match.group("version")
    filename = match.group("filename")

    return {
        "provider": provider,
        "component": component,
        "channel": channel,
        "base_version": base_version,
        "version": version,
        "filename": filename,
    }


def _build_nibuild_pull_url(metadata: dict) -> str:
    """Build the pull URL from the given metadata for nibuild provider."""
    component_dir = (
        metadata["component"][:4]
        if len(metadata["component"]) > 4
        else metadata["component"]
    )

    pull_url = (
        "https://pull.artifacts.ni.com/artifactory/rnd-{}-{}/{}/{}/{}/{}/{}".format(
            metadata["provider"],
            metadata["channel"],
            component_dir,
            metadata["component"],
            metadata["base_version"],
            metadata["version"],
            metadata["filename"],
        )
    )
    return pull_url


class NiArtifact(FetchMethod):
    """Class to fetch URIs via NI Artifactory."""

    provider_url_builders = {
        "nibuild": _build_nibuild_pull_url,
    }

    def _get_actual_download_url(self, url: str) -> str:
        """Get the actual download URL.

        The initial URL will redirect to a temporary URL for downloading the artifact.
        However, only the initial URL can be accessed with the authentication token.
        The redirected URL will fail if the authentication token is forwarded
        (default behavior of wget).
        """

        class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            """Custom handler to prevent automatic redirection."""

            def http_error_301(self, req, fp, code, msg, headers):
                raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

            def http_error_302(self, req, fp, code, msg, headers):
                raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

        opener = urllib.request.build_opener(NoRedirectHandler)
        urllib.request.install_opener(opener)

        headers = {
            "Authorization": f"Bearer {self.niartifacts_token}",
        }
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req):
                raise FetchError("Expected a redirect but got a successful response")
        except urllib.error.HTTPError as e:
            if e.code in (301, 302):
                return e.headers["Location"]
            else:
                raise
        finally:
            # Restore the default opener
            urllib.request.install_opener(urllib.request.build_opener())

    def check_certs(self, d):
        """Check whether to verify SSL certificates."""
        return (d.getVar("BB_CHECK_SSL_CERTS") or "1") != "0"

    def supports(self, ud, d):
        """Check to see if a given url can be fetched with niartifact."""
        return ud.type in ["niartifact"]

    def urldata_init(self, ud, d):
        """Initialize the urldata structure for niartifact fetches."""
        self.niartifacts_token = d.getVar("NIARTIFACTS_TOKEN")
        if not self.niartifacts_token:
            raise FetchError(
                "NIARTIFACTS_TOKEN is not set, cannot fetch from niartifact"
            )

        self.basecmd = d.getVar("FETCHCMD_wget") or "/usr/bin/env wget -t 2 -T 30"

        if not self.check_certs(d):
            self.basecmd += " --no-check-certificate"

        metadata = _parse_niartifact_uri(ud.url)
        url_builder_method = self.provider_url_builders.get(metadata["provider"])
        if not url_builder_method:
            raise FetchError(
                f"Unsupported provider '{metadata['provider']}' in niartifact URI"
            )
        self.pull_url = url_builder_method(metadata)
        self.actual_url = self._get_actual_download_url(self.pull_url)

        if "downloadfilename" in ud.parm:
            ud.basename = ud.parm["downloadfilename"]
        else:
            ud.basename = f"{metadata['component']}-{metadata['channel']}-{metadata['version']}.zip"

        dl_dir = d.getVar("DL_DIR")
        niartifact_dir = d.getVar("NIFETCH_NIARTIFACTS_DIR") or (
            dl_dir + "/niartifacts"
        )
        mkdirhier(niartifact_dir)

        ud.localfile = d.expand(niartifact_dir + "/" + ud.basename)

    def download(self, ud, d):
        """Download a file from niartifact."""
        cmd = f"{self.basecmd} -O {ud.localfile} '{self.actual_url}'"
        check_network_access(d, cmd, self.actual_url)

        runfetchcmd(cmd, d)

        return True
