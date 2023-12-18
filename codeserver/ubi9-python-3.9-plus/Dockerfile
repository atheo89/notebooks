ARG BASE_IMAGE
FROM ${BASE_IMAGE}

WORKDIR /opt/app-root/bin

# OS Packages needs to be installed as root
USER root

# Install usefull OS packages
RUN dnf install -y unixODBC postgresql

# Install MongoDB Client, We need a special repo for MongoDB as they do their own distribution
COPY mongodb-org-6.0.repo-x86_64 /etc/yum.repos.d/mongodb-org-6.0.repo

RUN dnf install -y mongocli

# Install MSSQL Client, We need a special repo for MSSQL as they do their own distribution
COPY mssql-2022.repo-x86_64 /etc/yum.repos.d/mssql-2022.repo

RUN ACCEPT_EULA=Y dnf install -y mssql-tools18 unixODBC-devel

ENV PATH="$PATH:/opt/mssql-tools18/bin"

# Other apps and tools installed as default user
USER 1001

WORKDIR /opt/app-root/src

