# The API's AWS resources. This branch creates only the database secret; the Lambda, its
# Function URL, the log group and the IAM role join it in m4/infra-api (spec 10.7).

# Neon's pooled connection string, for the Lambda.
#
# Terraform creates the parameter with a placeholder and then ignores its value forever.
# The real secret is written once, by hand:
#
#   aws ssm put-parameter --name /scrappy/prod/database_url --type SecureString \
#     --value 'postgresql+psycopg://...' --overwrite
#
# That keeps it out of Terraform state, out of plan output, and out of git. SSM Parameter
# Store's standard tier is free; Secrets Manager would charge $0.40 a month per secret and
# is on the prohibited list in spec section 14.
resource "aws_ssm_parameter" "database_url" {
  name        = "/scrappy/prod/database_url"
  description = "Neon pooled connection string for the Scrappy API"
  type        = "SecureString"
  value       = "placeholder"

  lifecycle {
    ignore_changes = [value]
  }
}

variable "app_version" {
  description = "Value served by /health. CI passes the commit SHA; locally it is just a label."
  type        = string
  default     = "local"
}

locals {
  api_name = "scrappy-api"
  # Built by backend/scripts/build_lambda.sh, and by CI with the same script.
  lambda_zip = "${path.module}/../backend/build/scrappy-api.zip"
}

# Created before the Lambda, and the Lambda depends on it: if the group does not exist at
# the first invocation, Lambda creates one itself with retention set to Never Expire, and
# the logs then accumulate forever (spec 10.7).
resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.api_name}"
  retention_in_days = 14
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.api_name}-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# Writing to CloudWatch Logs; nothing else.
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Reading the database URL — that one parameter, not every parameter in the account.
data "aws_iam_policy_document" "lambda_ssm" {
  statement {
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.database_url.arn]
  }
}

resource "aws_iam_role_policy" "lambda_ssm" {
  name   = "${local.api_name}-ssm-read"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda_ssm.json
}

resource "aws_lambda_function" "api" {
  function_name = local.api_name
  role          = aws_iam_role.lambda.arn

  runtime       = "python3.13"
  architectures = ["x86_64"]
  handler       = "app.main.handler"
  memory_size   = 512
  timeout       = 10

  filename = local.lambda_zip
  # Redeploys only when the package actually changes.
  source_code_hash = filebase64sha256(local.lambda_zip)

  environment {
    variables = {
      ENV                = "prod"
      APP_VERSION        = var.app_version
      DATABASE_URL_PARAM = aws_ssm_parameter.database_url.name

      # Until Cognito ships in M5 the live site has one shared pantry. settings.py refuses
      # to start in prod without this flag, so turning it on is always deliberate; both it
      # and AUTH_MODE change at M5 (spec 10.4).
      AUTH_MODE         = "shared"
      ALLOW_SHARED_MODE = "true"
    }
  }

  depends_on = [aws_cloudwatch_log_group.api]
}

# A public HTTPS address for the function. Free permanently, where API Gateway is free for
# only 12 months (spec section 7).
resource "aws_lambda_function_url" "api" {
  function_name = aws_lambda_function.api.function_name

  # The app verifies Cognito tokens itself from M5; IAM auth here would require every
  # browser request to be SigV4-signed, which a public web app cannot do.
  authorization_type = "NONE"

  # CORS lives here and nowhere else. FastAPI's CORSMiddleware runs only when ENV=local,
  # because two sets of headers make browsers reject the response (spec 10.7).
  cors {
    allow_origins = ["https://${aws_cloudfront_distribution.frontend.domain_name}", "http://localhost:5173"]
    allow_methods = ["GET", "POST", "DELETE"]
    allow_headers = ["authorization", "content-type"]
    max_age       = 3600
  }
}

# Anyone may call the function, but only through its URL: the FunctionUrlAuthType
# condition means this grant does not allow lambda:Invoke from the API or the CLI.
#
# Spec 10.7 claimed a second grant of lambda:InvokeFunction was also required. It is not,
# and AWS rejects it outright: "FunctionUrlAuthType is only supported for
# lambda:InvokeFunctionUrl". Verified October 17, 2026 — /health returns 200 with this
# grant alone.
resource "aws_lambda_permission" "function_url" {
  statement_id           = "AllowPublicFunctionUrlInvoke"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.api.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}
