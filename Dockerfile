# This Dockerfile is a copy of https://github.com/devcontainers/images/blob/main/src/python/.devcontainer/Dockerfile with a hardcoded variant, since the devcontainer is not yet available for python 3.13.2

FROM python:3.13.2

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    # Remove imagemagick due to https://security-tracker.debian.org/tracker/CVE-2019-10131
    && apt-get purge -y imagemagick imagemagick-6-common 

# Temporary: Upgrade python packages due to https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2022-40897 and https://github.com/advisories/GHSA-2mqj-m65w-jghx
# They are installed by the base image (python) which does not have the patch.
RUN python3 -m pip install --upgrade \
    setuptools==78.1.1 \
    gitpython==3.1.41
