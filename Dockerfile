FROM python:3.12.3-alpine

WORKDIR /app

# 1. Copy only the requirements file first to leverage Docker's layer caching
COPY requirements.txt .

# 2. Install dependencies globally inside the container
RUN pip install -r requirements.txt

# 3. Copy the rest of your application code
COPY . .

# 4. Run your application
CMD ["python3", "main.py"]