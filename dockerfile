# Use official Python runtime
FROM python:3.12

# Set working directory
WORKDIR /app

# Copy files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port (optional, for clarity)
EXPOSE 8080

# Command to run
CMD ["python", "app.py"]