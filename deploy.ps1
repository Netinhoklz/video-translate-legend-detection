# Deploy Script for Serverless Video App

# 1. Load Environment Variables from .env
Write-Host "Loading credentials from .env..."
$envPairs = @()
$reservedKeys = @("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_REGION", "AWS_EXECUTION_ENV", "AWS_LAMBDA_FUNCTION_NAME", "AWS_LAMBDA_FUNCTION_MEMORY_SIZE", "AWS_LAMBDA_FUNCTION_VERSION", "AWS_LAMBDA_INITIALIZATION_TYPE", "AWS_LAMBDA_LOG_GROUP_NAME", "AWS_LAMBDA_LOG_STREAM_NAME", "AWS_LAMBDA_RUNTIME_API", "LAMBDA_TASK_ROOT", "LAMBDA_RUNTIME_DIR")

Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        $key = $matches[1]
        $value = $matches[2]
        
        # Set locally for script usage
        [System.Environment]::SetEnvironmentVariable($key, $value, [System.EnvironmentVariableTarget]::Process)
        
        # Add to list for Lambda update ONLY if not reserved
        if ($reservedKeys -notcontains $key) {
            $envPairs += "$key=$value"
        }
    }
}

# Verify Credentials
if (-not $env:AWS_ACCESS_KEY_ID -or -not $env:AWS_SECRET_ACCESS_KEY) {
    Write-Error "AWS credentials not found in .env file!"
    exit 1
}

$REGION = $env:AWS_REGION
if (-not $REGION) { $REGION = "us-east-1" }

# 2. Get Account ID
Write-Host "Getting AWS Account ID..."
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
if (-not $ACCOUNT_ID) {
    Write-Error "Failed to get AWS Account ID. Check your credentials."
    exit 1
}
Write-Host "Account ID: $ACCOUNT_ID"
Write-Host "Region: $REGION"

# 2.1 Configure S3 CORS
$S3_BUCKET = $env:S3_BUCKET
if ($S3_BUCKET) {
    Write-Host "Configuring CORS for bucket '$S3_BUCKET'..."
    $corsConfig = '{"CORSRules": [{"AllowedHeaders": ["*"], "AllowedMethods": ["PUT", "POST", "GET"], "AllowedOrigins": ["*"], "ExposeHeaders": []}]}'
    # Write CORS config to temp file to avoid quoting issues
    $corsFile = [System.IO.Path]::GetTempFileName()
    $corsConfig | Out-File $corsFile -Encoding ASCII
    
    aws s3api put-bucket-cors --bucket $S3_BUCKET --cors-configuration "file://$corsFile" --region $REGION
    Remove-Item $corsFile
} else {
    Write-Host "WARNING: S3_BUCKET env var not set. Skipping CORS config."
}

# 3. ECR Login
Write-Host "Logging into ECR..."
$ECR_URL = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URL

# 4. Create Repository (if not exists)
$REPO_NAME = "video-processing-app-v2"
Write-Host "Ensuring ECR repository '$REPO_NAME' exists..."
aws ecr describe-repositories --repository-names $REPO_NAME --region $REGION > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating repository..."
    aws ecr create-repository --repository-name $REPO_NAME --region $REGION
} else {
    Write-Host "Repository already exists."
}

# 5. Build Docker Image
Write-Host "Building Docker image..."
# --provenance=false prevents creating OCI attestations that Lambda doesn't support yet
# --platform linux/amd64 ensures compatibility with x86_64 Lambda functions
# --no-cache forces a clean build to ensure Dockerfile changes are picked up
docker build --provenance=false --platform linux/amd64 -f Dockerfile.lambda -t $REPO_NAME .

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker build failed! Please check the error messages above."
    exit 1
}

# 6. Tag Image
Write-Host "Tagging image..."
docker tag "$REPO_NAME`:latest" "$ECR_URL/$REPO_NAME`:latest"

# 7. Push Image
Write-Host "Pushing image to ECR..."
docker push "$ECR_URL/$REPO_NAME`:latest"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker push failed! Please check the error messages above."
    exit 1
}

# 8. Update Lambda Function Code
$FUNCTION_NAME = "trabalho_nuvem_final" 
Write-Host "Updating Lambda function CODE for '$FUNCTION_NAME'..."
aws lambda update-function-code --function-name $FUNCTION_NAME --image-uri "$ECR_URL/$REPO_NAME`:latest" --region $REGION > $null 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "Lambda function code updated successfully!"
    
    # Wait for the update to complete to avoid ResourceConflictException
    Write-Host "Waiting for Lambda function update to complete..."
    aws lambda wait function-updated --function-name $FUNCTION_NAME --region $REGION

    # 9. Update Lambda Configuration (Memory, Timeout, Env Vars)
    Write-Host "Updating Lambda CONFIGURATION (Memory: 3008MB, Timeout: 5m, EnvVars)..."
    
    # Construct Environment Variables String
    # Format: Variables={Key1=Value1,Key2=Value2}
    $envString = "Variables={" + ($envPairs -join ",") + "}"
    
    aws lambda update-function-configuration `
        --function-name $FUNCTION_NAME `
        --region $REGION `
        --memory-size 3008 `
        --timeout 300 `
        --environment $envString

    if ($LASTEXITCODE -eq 0) {
        Write-Host "Lambda configuration updated successfully!"
    } else {
        Write-Host "WARNING: Failed to update Lambda configuration."
    }
    
    # 10. Get Function URL
    Write-Host "Retrieving Function URL..."
    $funcUrlConfig = aws lambda get-function-url-config --function-name $FUNCTION_NAME --region $REGION 2>$null | ConvertFrom-Json
    if ($funcUrlConfig) {
        $FUNC_URL = $funcUrlConfig.FunctionUrl
        Write-Host "--------------------------------------------------"
        Write-Host "Deployment Complete!"
        Write-Host "Image URI: $ECR_URL/$REPO_NAME`:latest"
        Write-Host "Function URL: $FUNC_URL"
        Write-Host "--------------------------------------------------"
    } else {
        Write-Host "--------------------------------------------------"
        Write-Host "Deployment Complete!"
        Write-Host "Image URI: $ECR_URL/$REPO_NAME`:latest"
        Write-Host "Function URL: (Not configured or could not retrieve)"
        Write-Host "--------------------------------------------------"
    }

} else {
    Write-Host "WARNING: Could not update Lambda function automatically."
    Write-Host "Make sure the function name is '$FUNCTION_NAME' or update the script."
    Write-Host "You can manually update it in the AWS Console -> Image -> Deploy new image."
}
