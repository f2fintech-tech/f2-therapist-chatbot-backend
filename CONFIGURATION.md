# RAG Pipeline Configuration Guide

## Environment Variables Setup

Create a `.env` file in the project root directory with the following variables:

### Example .env file:
```bash
# Google Gemini Configuration
# Get your API key from: https://ai.google.dev/
GEMINI_API_KEY=your-actual-gemini-api-key-here

# Pinecone Configuration
# Get your API key from: https://www.pinecone.io/
PINECONE_API_KEY=your-actual-pinecone-api-key-here
PINECONE_INDEX_NAME=f2-therapy-index

# AWS S3 Configuration
# Get credentials from AWS IAM: https://console.aws.amazon.com/
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1
S3_BUCKET_NAME=f2-fintech-kb

# Database Configuration (Optional, for persistence)
DATABASE_URL=postgresql://user:password@localhost:5432/f2_therapist
REDIS_URL=redis://localhost:6379/0

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=logs/rag_pipeline.log
```

## Step-by-Step Configuration

### 1. Get Gemini API Key

**Steps:**
1. Visit https://ai.google.dev/
2. Click "Get API key" or "Google AI Studio"
3. Create a new API key
4. Copy the key and add to `.env`:
   ```bash
   GEMINI_API_KEY=gsk_xxx...
   ```

**Verify:**
```bash
python3 -c "
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()
print('✓ Gemini API configured successfully')
"
```

### 2. Setup Pinecone Vector Database

**Steps:**
1. Sign up at https://www.pinecone.io/
2. Create a project
3. Create an index with:
   - **Name:** `f2-therapy-index`
   - **Dimension:** `768` (matches Gemini embeddings)
   - **Metric:** `cosine`
   - **Pod Type:** Starter or Standard
4. Copy API key and add to `.env`:
   ```bash
   PINECONE_API_KEY=xxx-xxx-xxx...
   ```

**Verify:**
```bash
python3 -c "
from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()
pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
print('Pinecone indexes:', [idx.name for idx in pc.list_indexes()])
"
```

### 3. Setup AWS S3 (Optional, for data storage)

**Steps:**
1. Create AWS account at https://aws.amazon.com/
2. Create an IAM user:
   - Go to IAM → Users → Create user
   - Attach policy: `AmazonS3FullAccess`
3. Create access keys for the user:
   - In User details → Security credentials → Create access key
4. Create an S3 bucket:
   - Name: `f2-fintech-kb` (or your preferred name)
   - Region: `us-east-1`
5. Add credentials to `.env`:
   ```bash
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=xxx...
   AWS_REGION=us-east-1
   S3_BUCKET_NAME=f2-fintech-kb
   ```

**Verify:**
```bash
python3 -c "
import boto3
from dotenv import load_dotenv

load_dotenv()
s3 = boto3.client('s3')
buckets = s3.list_buckets()
print('S3 Buckets:', [b['Name'] for b in buckets['Buckets']])
"
```

### 4. Setup Database (Optional, for conversation persistence)

**For PostgreSQL:**
```bash
# Install PostgreSQL
# Ubuntu/Debian:
sudo apt-get install postgresql postgresql-contrib

# macOS:
brew install postgresql

# Start PostgreSQL service
sudo service postgresql start  # Ubuntu
brew services start postgresql  # macOS
```

**Create database:**
```bash
createuser f2_user
createdb -O f2_user f2_therapist
psql -U f2_user -d f2_therapist < init.sql
```

**Add to .env:**
```bash
DATABASE_URL=postgresql://f2_user:password@localhost:5432/f2_therapist
```

### 5. Setup Redis (Optional, for caching)

```bash
# Install Redis
# Ubuntu/Debian:
sudo apt-get install redis-server

# macOS:
brew install redis

# Start Redis
redis-server

# Add to .env:
REDIS_URL=redis://localhost:6379/0
```

## Configuration Files

### config.yaml
Central configuration for all modules:

```yaml
google:
  api_key: "${GEMINI_API_KEY}"
  embedding_model: "models/text-embedding-004"
  chat_model: "gemini-3.1-flash"

pinecone:
  api_key: "${PINECONE_API_KEY}"
  index_name: "f2-therapy-index"
  dimension: 768
  metric: "cosine"

rag:
  chunk_size: 1000
  chunk_overlap: 100
  top_k: 3

aws:
  region: "${AWS_REGION}"
  bucket_name: "${S3_BUCKET_NAME}"

database:
  url: "${DATABASE_URL}"

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

## Validation Checklist

Before running the RAG pipeline, verify:

- [ ] `.env` file exists in project root
- [ ] `GEMINI_API_KEY` is set and valid
- [ ] `PINECONE_API_KEY` is set and valid
- [ ] Pinecone index `f2-therapy-index` exists with dimension 768
- [ ] S3 bucket exists (if using S3)
- [ ] Raw data files exist in `src/data/raw/`
- [ ] Python 3.9+ is installed
- [ ] All dependencies from `requirements.txt` are installed

**Run validation:**
```bash
python3 -c "
import os
from dotenv import load_dotenv

load_dotenv()

required_vars = ['GEMINI_API_KEY', 'PINECONE_API_KEY']
for var in required_vars:
    if not os.getenv(var):
        print(f'✗ Missing: {var}')
    else:
        print(f'✓ {var} set')
"
```

## Troubleshooting

### Issue: ModuleNotFoundError
**Solution:**
```bash
# Install dependencies
pip install -r requirements.txt

# Install additional packages
pip install google-generativeai
pip install pinecone-client
pip install boto3
```

### Issue: GEMINI_API_KEY not found
**Solution:**
```bash
# Verify .env is in correct location
ls -la .env

# Check it contains the API key
cat .env | grep GEMINI_API_KEY

# Reload environment
unset GEMINI_API_KEY
source .env
echo $GEMINI_API_KEY
```

### Issue: Cannot connect to Pinecone
**Solution:**
```bash
# Verify API key is correct
# Check index exists and is running
# Verify network connectivity

python3 -c "
from pinecone import Pinecone
import os
pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
indexes = pc.list_indexes()
print('Indexes:', indexes)
"
```

### Issue: S3 bucket not found
**Solution:**
```bash
# List buckets to verify AWS credentials
aws s3 ls

# Create bucket if needed
aws s3 mb s3://f2-fintech-kb --region us-east-1
```

## Security Best Practices

1. **Never commit .env file to version control**
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   ```

2. **Rotate API keys regularly**
   - Update keys in provider dashboards
   - Update .env file

3. **Use IAM roles for AWS**
   - Avoid hardcoding credentials
   - Use role-based access

4. **Limit API key permissions**
   - Only grant necessary permissions
   - Use separate keys for different services

5. **Monitor API usage**
   - Set up billing alerts
   - Track API calls and costs

## Performance Tuning

### Optimize Gemini API calls:
```python
# Cache embeddings for frequently used text
embedding_cache = {}

def get_cached_embedding(text):
    if text not in embedding_cache:
        embedding_cache[text] = embed_text(text)
    return embedding_cache[text]
```

### Optimize Pinecone queries:
```python
# Increase batch size for bulk operations
vectors = [...]  # Large list of vectors
index.upsert(vectors=vectors, batch_size=100)
```

### Optimize data processing:
```python
# Use parallel processing for large datasets
from multiprocessing import Pool

with Pool(processes=4) as pool:
    results = pool.map(process_item, large_dataset)
```

## Monitoring and Logging

Configure logging in your Python code:

```python
import logging
import logging.handlers

# Create logs directory
import os
os.makedirs('logs', exist_ok=True)

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# File handler
fh = logging.handlers.RotatingFileHandler(
    'logs/rag_pipeline.log',
    maxBytes=10485760,  # 10MB
    backupCount=10
)

# Console handler
ch = logging.StreamHandler()

# Formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
fh.setFormatter(formatter)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)
```

## Next Steps

1. Configure all required environment variables
2. Run validation checklist
3. Execute the RAG pipeline
4. Monitor logs for any issues
5. Deploy to production with appropriate security measures
