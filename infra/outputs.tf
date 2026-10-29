output "site_url" {
  description = "The public URL of the deployed frontend."
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "frontend_bucket" {
  description = "Bucket the built frontend is uploaded to."
  value       = aws_s3_bucket.frontend.id
}

output "cloudfront_distribution_id" {
  description = "Needed to invalidate the cache after a deploy."
  value       = aws_cloudfront_distribution.frontend.id
}

output "api_url" {
  description = "Public HTTPS address of the API; the frontend's VITE_API_URL."
  value       = aws_lambda_function_url.api.function_url
}

output "deploy_role_arn" {
  description = "Set this as the AWS_DEPLOY_ROLE_ARN repository variable in GitHub."
  value       = aws_iam_role.github_deploy.arn
}

output "cognito_user_pool_id" {
  description = "VITE_COGNITO_USER_POOL_ID for the frontend build."
  value       = aws_cognito_user_pool.users.id
}

output "cognito_client_id" {
  description = "VITE_COGNITO_CLIENT_ID for the frontend build."
  value       = aws_cognito_user_pool_client.web.id
}
