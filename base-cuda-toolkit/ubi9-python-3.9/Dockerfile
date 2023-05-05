FROM registry.redhat.io/rhel:latest
#docker.io/nvidia/cuda:12.1.1-base-ubi9
#registry.redhat.io/rhel:latest
#registry.access.redhat.com/ubi9/python-39:latest


# USER 0


# # Add NVIDIA CUDA repository
# RUN curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/rhel7/x86_64/cuda-rhel7.repo | \
#     tee /etc/yum.repos.d/cuda.repo

# RUN yum clean all && \
#     yum -y module install nvidia-driver:latest-dkms && \
#     yum -y install cuda

# # Install CUDA Toolkit and cuDNN library
# # RUN yum clean all && \
# #     yum -y update && \
# #     yum -y install \
# #         cuda-11-4 \
# #         libcudnn8-devel-8.2.4.15-1.cuda11.4 \
# #         libcudnn8-8.2.4.15-1.cuda11.4

# # Set environment variables for CUDA Toolkit
# ENV PATH /usr/local/cuda/bin:$PATH
# ENV LD_LIBRARY_PATH /usr/local/cuda/lib64:$LD_LIBRARY_PATH

# # Verify installation
# RUN nvcc --version && \
#     echo "Testing CUDA installation..." && \
#     cd /usr/local/cuda/samples/1_Utilities/deviceQuery && \
#     make && \
#     ./deviceQuery

# CMD ["/bin/bash"]
