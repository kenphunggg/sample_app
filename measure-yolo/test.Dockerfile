# 1. Base Image - Consider checking for a newer version from nvcr.io for security/performance updates.
FROM nvcr.io/nvidia/pytorch:21.10-py3

# 2. Set Environment Variables - Use ENV so it persists.
# This fixes potential encoding issues with libraries like OpenCV.
ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    LC_CTYPE=en_US.UTF-8

# 3. Set up the working directory early. This is a good practice.
WORKDIR /detection

# 4. Install dependencies FIRST to leverage the Docker build cache.
# Copy only the requirements file. This layer will only be rebuilt if requirements.txt changes.
COPY requirements.txt .

# Upgrade pip and install all Python requirements in a single RUN command to reduce layers.
RUN python3 -m pip install --no-cache-dir --upgrade pip wheel && \
    pip3 install --no-cache-dir -r requirements.txt

# 5. NOW, copy the application code.
# This layer will be rebuilt when your code changes, but the step above will be cached.
# The '.' copies everything from the build context to the current WORKDIR.
# It's best practice to use a .dockerignore file to exclude unnecessary files.
COPY . .

# 6. Run any setup needed by your application and make the run script executable.
# Chaining these also reduces layers.
RUN python3 setup.py && \
    chmod +x run.sh

# 7. Expose the port and define the runtime command.
EXPOSE 8080
CMD ["./run.sh"]
